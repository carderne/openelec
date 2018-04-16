import numpy as np
import pandas as pd
from astroML.clustering import HierarchicalClustering, get_graph_segments
from shapely.geometry import Point, LineString
from math import sqrt
import folium
import geopandas as gpd

def run_mgo_model(minimum_area_m2, demand_multiplier, price_pv_multiplier, price_wire, price_conn, price_maintenance, years, max_tot_length):

    minimum_area_m2 = float(minimum_area_m2)
    demand_multiplier = float(demand_multiplier)
    price_pv_multiplier = float(price_pv_multiplier)
    price_wire = float(price_wire)
    price_conn = float(price_conn)
    price_maintenance = float(price_maintenance)
    years = float(years)
    max_tot_length = float(max_tot_length)

    input_file = 'uploads/input.shp'

    buildings = gpd.read_file(input_file)
    buildings_projected = buildings.copy()
    # This is the Africa Albers Equal Area Conic EPSG: 102022
    epsg102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
    buildings_projected = buildings_projected.to_crs(epsg102022)

    buildings_projected["area_m2"] = buildings_projected['geometry'].area
    buildings_points = buildings_projected.copy()
    buildings_points.geometry = buildings_points['geometry'].centroid
    buildings_points['X'] = buildings_points.geometry.x
    buildings_points['Y'] = buildings_points.geometry.y

    x_mean = buildings.geometry.centroid.x.mean()
    y_mean = buildings.geometry.centroid.y.mean()

    latitude = -9.6295
    longitude = 39.1812


    df = pd.DataFrame(buildings_points)
    df = df.loc[df['area_m2'] > minimum_area_m2]

    pv_point = gpd.GeoDataFrame(crs={'init': 'epsg:4326'}, geometry=[Point([longitude, latitude])])
    pv_point_projected = pv_point.copy()
    pv_point_projected = pv_point_projected.to_crs(epsg102022)
    pv_point_df = [{'X': pv_point_projected.geometry.x, 'Y': pv_point_projected.geometry.y, 'area_m2': 0}]
    df = pd.concat([pd.DataFrame(pv_point_df), df], ignore_index=True)
    points = df[['X', 'Y']].as_matrix()

    model = HierarchicalClustering(n_neighbors=10, edge_cutoff=0.9, min_cluster_size=10)
    model.fit(points)
    T_x, T_y = get_graph_segments(model.X_train_, model.full_tree_)

    df['income'] = df['area_m2'].astype(int) * demand_multiplier
    nodes = df[['X', 'Y', 'income']].reset_index().values.astype(int).tolist()
    for node in nodes:
        # add default 0's for marg_dist, tot_dist and connected
        node.extend([0, 0, 0])
        

    counter = 0
    network_undirected = []
    for xs, ys, xe, ye in zip(T_x[0], T_y[0], T_x[1], T_y[1]):
        network_undirected.append([counter, int(xs), int(ys), int(xe), int(ye), -99, -99, 0, 0, 1])
        counter += 1
        
    # add the length for each arc
    for arc in network_undirected:
        arc[8] = sqrt((arc[3] - arc[1])**2 + (arc[4] - arc[2])**2)


    def direct_network(nodes, network, index):
        for arc in network:
            found = False
            if arc[1] == nodes[index][1] and arc[2] == nodes[index][2]:
                # make sure we haven't done this arc already!
                if arc[7] == 1:
                    continue
                found = True
                
            elif arc[3] == nodes[index][1] and arc[4] == nodes[index][2]:
                # make sure we haven't done this arc already!
                if arc[7] == 1:
                    continue
                found = True
                
                # flip it around because it's pointing the wrong way
                xs_new = arc[3]
                ys_new = arc[4]
                arc[3] = arc[1]
                arc[4] = arc[2]
                arc[1] = xs_new
                arc[2] = ys_new
                
            if found:    
                arc[5] = nodes[index][0] # tell this arc that this node is its starting point
                arc[7] = 1 # so we know this arc has been done
                arc_index = arc[0] # store arc index to find point at the other end
                
                for node in nodes:
                    if node[1] == arc[3] and node[2] == arc[4]:
                        arc[6] = node[0] # tell this arc that this node is its ending point
                        node[4] = arc[8] # assign arc length to node's marginal distance
                        node[5] = nodes[index][5] + arc[8] # and calculate total distance
                        
                        # If this building exceeds the maximum total length allowed, disable the arc connecting it
                        # The later algorithms respect this settings
                        if node[5] > max_tot_length:
                            arc[9] = 0
                        
                        nodes, network = direct_network(nodes, network, node[0]) # and investigate downstream from this node
                        break
        
        return nodes, network

    # network_undirected seems to also be modified, which could be dangerous!

    nodes, network_directed = direct_network(nodes, network_undirected, 0)

    # for every node, add references to every arc that connects to it
    for arc in network_directed:
        nodes[arc[5]].append(arc[0])
        nodes[arc[6]].append(arc[0])

    def calculate_profit(nodes, network, index, disabled_arc_index, cost, income):
        # here we recurse through the network and calculate profit
        # start with all arcs that connect to the index node, and get the end-nodes for those arcs
        # calculate profit on those nodes, and then recurse!
        # disabled_arc should be treated as if disabled
        
        # first calculate tehe profitability of thise node?
        cost += price_wire * nodes[index][4] + price_conn
        income += nodes[index][3]
        
        connected_arcs = [network[arc_index] for arc_index in nodes[index][7:]]
        for arc in connected_arcs:
            if arc[9] == 1 and arc[0] != disabled_arc_index and arc[5] == index:
                cost, income, nodes, network = calculate_profit(nodes, network, arc[6], disabled_arc_index, cost, income)
                
        return cost, income, nodes, network


    price_pv = df['area_m2'].sum() * price_pv_multiplier
    counter = 0

    most_profitable = -9999999
    while True:
        found = False
        for arc in network_directed:
            # use a recursive function to calculate profitability of network
            # this should all be done in a temporary network variable
            # and indicate that this arc should be treated as if disabled
            cost, income, nodes, network = calculate_profit(nodes, network_directed, 0, arc[0], 0, 0)

            capex = price_pv + cost
            opex = (price_maintenance * capex) * years
            total_income = income * years
            profit = total_income - capex - opex
            
            counter += 1
            
            # check if this is the most profitableb yet
            if profit > most_profitable:
                found = True
                most_profitable = profit
                most_profitable_index = arc[0]
        if found:
            # disable that arc
            network_directed[most_profitable_index][9] = 0

        # now repeat the above steps for the whole network again
        # until we go through without finding a more profitable setup than what we already have
        else:
            break
            
    # now we need to tell the houses that aren't connected, that they aren't connected (or vice-versa)
    # recurse from the starting point and ID connected houses as connected?
    def connect_houses(nodes, network, index):
        # start from base, follow connection (similar to calculate_profit) and swith node[6] to 1 wherever connected
        # and only follow the paths of connected houses
        
        # this node is connected
        nodes[index][6] = 1
        
        connected_arcs = [network[arc_index] for arc_index in nodes[index][7:]]
        for arc in connected_arcs:
            if arc[9] == 1 and arc[5] == index:
                connect_houses(nodes, network, arc[6])
                
        return nodes, network
        
    nodes, network_directed = connect_houses(nodes, network_directed, 0)

    # and do the same for the stranded arcs
    for node in nodes:
        if node[6] == 0:
            connected_arcs = [network[arc_index] for arc_index in node[7:]]
            for arc in connected_arcs:
                arc[9] = 0


    # create a quick report
    # number connected, length of line, total profit over ten years
    count_nodes = 0
    income = 0
    for node in nodes:
        if node[6] == 1:
            count_nodes += 1
            income += node[3]

    total_length = 0.0
    total_potential_length = 0.0
    for arc in network_directed:
        if arc[9] == 1:
            total_length += arc[8]
        total_potential_length += arc[8]

    capex = price_pv + price_conn * count_nodes + total_length * price_wire
    opex = (price_maintenance * capex) * years
    total_income = income * years


    # join the resultant points with the orignal buildings_projected
    nodes_for_df = [node[0:7] for node in nodes]
    nodes_df = pd.DataFrame(columns=['idx', 'X', 'Y', 'income', 'marg_dist', 'tot_dist',
                                      'connected'], data=nodes_for_df)
    nodes_geometry = [Point(xy) for xy in zip(nodes_df['X'], nodes_df['Y'])]
    nodes_gdf = gpd.GeoDataFrame(nodes_df, crs=buildings_projected.crs, geometry=nodes_geometry)

    network_df = pd.DataFrame(columns=['idx', 'xs', 'ys', 'xe', 'ye', 'node_start', 'node_end',
                                       'directed', 'length', 'enabled'], data=network)
    LineString([(arc[1], arc[2]), (arc[3], arc[4])])
    network_geometry = [LineString([(arc[1], arc[2]), (arc[3], arc[4])]) for arc in network]
    network_gdf = gpd.GeoDataFrame(network_df, crs=buildings_projected.crs, geometry=network_geometry)

    buildings_joined = gpd.sjoin(buildings_projected, nodes_gdf)


    # project back to an unprojected (i.e., in degrees) CRS
    network_wgs84 = network_gdf.copy()
    network_wgs84 = network_wgs84.to_crs(epsg=4326)
    network_wgs84 = network_wgs84.loc[network_wgs84['enabled'] == 1]

    buildings_wgs84 = buildings_joined.copy()
    buildings_wgs84 = buildings_wgs84.to_crs(epsg=4326)
    buildings_wgs84 = buildings_wgs84.loc[buildings_wgs84['connected'] == 1]

    nodes_wgs84 = nodes_gdf.copy()
    nodes_wgs84 = nodes_wgs84.to_crs(epsg=4326)
    nodes_wgs84 = nodes_wgs84.loc[nodes_wgs84['connected'] == 1]

    output_map = folium.Map([y_mean, x_mean], zoom_start=15)

    for index, row in network_wgs84.iterrows():
        # Can't use row.geometry.coords because Folium interprets X and Y the other way around, for whatever reason
        coords = list(row.geometry.coords)
        xs = coords[0][0]
        ys = coords[0][1]
        xe = coords[1][0]
        ye = coords[1][1]
        folium.PolyLine([(ys, xs), (ye, xe)]).add_to(output_map)

    folium.Marker([latitude, longitude]).add_to(output_map)
    
    output_file = f'static/output_map{counter}.html'
    output_map.save(output_file)
    return output_file

