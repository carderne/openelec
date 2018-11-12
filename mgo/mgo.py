# # Mini Grid Optimiser
# Tool designed to take a small village and estimate the optimum connections, based on a PV installation location and economic data.
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from astroML.clustering import HierarchicalClustering, get_graph_segments
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from math import sqrt
import folium
import geopandas as gpd
import os.path
from collections import defaultdict

# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'

def village_centroids(villages_path):
    villages = defaultdict(tuple)

    for file in os.listdir(villages_path):
        if file.endswith('.geojson'):

            name = os.path.splitext(file)[0]

            gdf = gpd.read_file(os.path.join(villages_path, file))
            lng = gdf.geometry.centroid.x.mean()
            lat = gdf.geometry.centroid.y.mean()

            villages[name] = {'lat': lat, 'lng': lng}

    return villages


def load_buildings(village, file_dir, min_area):
    min_area = float(min_area)
    input_file = '{}/{}.geojson'.format(file_dir, village)
    buildings = gpd.read_file(input_file)
    
    buildings_projected = buildings.to_crs(EPSG102022)

    buildings_projected["area"] = buildings_projected['geometry'].area
    buildings_projected = buildings_projected.loc[buildings_projected['area'] > min_area]

    buildings = buildings_projected.to_crs(epsg=4326)
    buildings = buildings.reset_index().drop(columns=['index'])

    return buildings


def create_network(buildings, gen_lat, gen_lng, max_length):
    gen_lat = float(gen_lat)
    gen_lng = float(gen_lng)
    max_tot_length = float(max_length)
    
    # This is the Africa Albers Equal Area Conic EPSG: 102022
    epsg102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
    buildings_projected = buildings.to_crs(EPSG102022)

    buildings_points = buildings_projected.copy()
    buildings_points.geometry = buildings_points['geometry'].centroid
    buildings_points['X'] = buildings_points.geometry.x
    buildings_points['Y'] = buildings_points.geometry.y

    # ### We then take all the houses and calculate the optimum network that connects them all to the PV point, before we start analysing further and deciding on the optimum network.
    df = pd.DataFrame(buildings_points)

    pv_point = gpd.GeoDataFrame(crs={'init': 'epsg:4326'}, geometry=[Point([gen_lng, gen_lat])])
    pv_point_projected = pv_point.copy()
    pv_point_projected = pv_point_projected.to_crs(EPSG102022)
    pv_point_df = [{'X': pv_point_projected.geometry.x, 'Y': pv_point_projected.geometry.y, 'area': 0}]
    df = pd.concat([pd.DataFrame(pv_point_df), df], ignore_index=True)
    points = df[['X', 'Y']].as_matrix()
    
    min_cluster = len(df.index) - 1
    if min_cluster >= 2:
        model = HierarchicalClustering(n_neighbors=min_cluster, edge_cutoff=0.9, min_cluster_size=min_cluster)
        model.fit(points)
        T_x, T_y = get_graph_segments(model.X_train_, model.full_tree_)
    else:
        # in this case there will be no network
        # need to handle somehow?
        pass
        
    # Structure for network:
    # 0   index
    # 1   xs
    # 2   ys
    # 3   xe
    # 4   ye
    # 5   node index first point
    # 6   node index last point
    # 7   whether this arc is directed (0 or 1)
    # 8   arc length
    # 9   whether enabled (default to 1)

    # Structure for nodes:
    # The PV point is indexed at point 0
    # 0   index
    # 1   x
    # 2   y
    # 3   area_m2
    # 4   marginal distance
    # 5   total distance
    # 6   connected (default to 0)
    # 7.. connected arc indices

    # ### This point and line data is then copied into two arrays, called *nodes* and *network*, containing the houses and lines, respectively.
    # Each element represents a single house or joining arc, and has data within describing the coordinates and more.
    # astype(int) doesn't round - it just chops off the decimals
    nodes = df[['X', 'Y', 'area']].reset_index().values.astype(int).tolist()
    for node in nodes:
        # add default 0's for marg_dist, tot_dist and connected
        node.extend([0, 0, 0])
        

    counter = 0
    network = []
    for xs, ys, xe, ye in zip(T_x[0], T_y[0], T_x[1], T_y[1]):
        network.append([counter, int(xs), int(ys), int(xe), int(ye), -99, -99, 0, 0, 1])
        counter += 1
        
    # add the length for each arc
    for arc in network:
        arc[8] = sqrt((arc[3] - arc[1])**2 + (arc[4] - arc[2])**2)


    # ### Then we need to calculate the directionality of the network, starting from the PV location and reaching outwards to the furthest branches.
    # We use this to calculate, for each node, it's marginal and total distance from the PV location.
    # At the same time, we tell each arc which node is 'upstream' of it, and which is 'downstream'.
    # We also tell each node which arcs (at least one, up to three or four?) it is connected to.
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

    # network seems to also be modified, which could be dangerous!

    nodes, network = direct_network(nodes, network, 0)

    # for every node, add references to every arc that connects to it
    for arc in network:
        nodes[arc[5]].append(arc[0])
        nodes[arc[6]].append(arc[0])

    return network, nodes


def run_model(network, nodes, demand, tariff, gen_cost, cost_wire, cost_connection,
              opex_ratio, years, discount_rate, target_coverage=-1):

    
    demand_per_person_kwh_month = float(demand)
    tariff = float(tariff)
    gen_cost_per_kw = float(gen_cost)
    cost_wire = float(cost_wire)
    cost_connection = float(cost_connection)
    opex_ratio = float(opex_ratio) / 100  # because user specifies as %
    years = int(years)
    discount_rate = float(discount_rate) / 100  # because user specifies as %

    # ### Here we prepare the algorithm to optimise our network configuration, by pruning network extensions that aren't profitable.
    # Here the economic data should be entered.
    # optimisation strategy #2
    # cut arcs one by one, see which cut is the *most* profitable, and then take that network and repeat the process
    # annual income should be specified by the nodes

    num_people_per_m2 = 0.15  # bit of a guess that there are 4 people in 40m2 house
    demand_per_person_kw_peak = demand_per_person_kwh_month / (4*30)  # 130 is based on MTF numbers, should use a real demand curve
    gen_size_kw = sum([n[3] for n in nodes]) * num_people_per_m2 * demand_per_person_kw_peak
    cost_gen = gen_size_kw * gen_cost_per_kw


    def calculate_profit(nodes, network, index, disabled_arc_index, cost, income_per_month):
        # here we recurse through the network and calculate profit
        # start with all arcs that connect to the index node, and get the end-nodes for those arcs
        # calculate profit on those nodes, and then recurse!
        # disabled_arc should be treated as if disabled
        
        # first calculate tehe profitability of thise node?
        cost += cost_wire * nodes[index][4] + cost_connection
        income_per_month += nodes[index][3] * num_people_per_m2 * demand_per_person_kwh_month * tariff
        
        connected_arcs = [network[arc_index] for arc_index in nodes[index][7:]]
        for arc in connected_arcs:
            if arc[9] == 1 and arc[0] != disabled_arc_index and arc[5] == index:
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, arc[6], disabled_arc_index, cost, income_per_month)
                
        return cost, income_per_month, nodes, network


    # ### Then we start with the complete network, and try 'deleting' each arc.
    # Whichever deletion is the most profitable, we make it permanent and repeat the process with the new configuration.
    # This continues until there are no more increases in profitability to be had.

    if target_coverage == -1:
        best_npv = -9999999
        counter = 0
        while True:
            found = False
            for arc in network:
                # use a recursive function to calculate profitability of network
                # this should all be done in a temporary network variable
                # and indicate that this arc should be treated as if disabled
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, 0, arc[0], 0, 0)

                capex = cost_gen + cost
                opex = (opex_ratio * capex)
                income = income_per_month * 12
                profit = income - capex - opex
                
                flows = np.ones(years) * (income - opex)
                flows[0] = -capex
                npv = np.npv(discount_rate, flows)
                
                counter += 1
                
                # check if this is the most profitable yet
                if npv > best_npv:
                    found = True
                    best_npv = npv
                    best_npv_index = arc[0]
            if found:
                # disable that arc
                network[best_npv_index][9] = 0

            # now repeat the above steps for the whole network again
            # until we go through without finding a more profitable setup than what we already have
            else:
                break
    else:
        total_arcs = len(network)
        actual_coverage = 1  # to start with
        
        counter = 0
        while True:
            best_npv = -9999999
            found = False
            for arc in network:
                # use a recursive function to calculate profitability of network
                # this should all be done in a temporary network variable
                # and indicate that this arc should be treated as if disabled
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, 0, arc[0], 0, 0)
        
                capex = cost_gen + cost
                opex = (opex_ratio * capex)
                income = income_per_month * 12
                profit = income - capex - opex
                
                flows = np.ones(years) * (income - opex)
                flows[0] = -capex
                npv = np.npv(discount_rate, flows)
                
                counter += 1
        
                # check if this is the most profitable yet
                if npv > best_npv and arc[9] == 1:
                    found = True
                    best_npv = npv
                    best_npv_index = arc[0]
                    
            if found:
                # disable that arc
                network[best_npv_index][9] = 0
        
            actual_coverage = len([arc for arc in network if arc[9] == 1])/total_arcs
            if actual_coverage <= target_coverage:
                break
                                
    # ### Then we disconnect all the houses that are no longer served by active arcs, and prune any stranded arcs that remained on un-connected paths.
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
        
    nodes, network = connect_houses(nodes, network, 0)

    # and do the same for the stranded arcs
    for node in nodes:
        if node[6] == 0:
            connected_arcs = [network[arc_index] for arc_index in node[7:]]
            for arc in connected_arcs:
                arc[9] = 0


    # ### And calculate some quick summary numbers for the village
    # create a quick report
    # number connected, length of line, total profit over ten years
    count_nodes = 0
    income_per_month = 0
    gen_size_kw = 0
    for node in nodes:
        if node[6] == 1:
            count_nodes += 1
            income_per_month += node[3] * num_people_per_m2 * demand_per_person_kwh_month * tariff
            gen_size_kw += node[3] * num_people_per_m2 * demand_per_person_kw_peak
    
    count_nodes -= 1  # so we don't count the generator

    total_length = 0.0
    for arc in network:
        if arc[9] == 1:
            total_length += arc[8]

    capex = gen_size_kw * gen_cost_per_kw + cost_connection * count_nodes + cost_wire * total_length
    opex = (opex_ratio * capex)
    income = income_per_month * 12

    flows = np.ones(years) * (income - opex)
    flows[0] = -capex
    npv = np.npv(discount_rate, flows)

    results = {'connected': count_nodes,
               'gen_size': int(gen_size_kw),
               'length': int(total_length),
               'capex': int(capex),
               'opex': int(opex),
               'income': int(income),
               'npv': int(npv)}

    return results, network, nodes


def network_to_spatial(buildings, network, nodes):
    # ### And then do a spatial join to get the results back into a polygon shapefile
    # join the resultant points with the orignal buildings_projected
    # create geometries from X and Y points and create gdf
    nodes_for_df = [node[0:7] for node in nodes] # drop the extra columsn that will confuse a df
    nodes_df = pd.DataFrame(columns=['index', 'X', 'Y', 'area', 'marg_dist', 'tot_dist',
                                      'connected'], data=nodes_for_df)
    nodes_df.index = nodes_df.index - 1  # to get rid of pv point
    nodes_df = nodes_df.drop(columns=['area'])  # otherwise left and right in join have area in them
    buildings_joined = buildings.merge(nodes_df, left_index=True, right_index=True)
    buildings_joined = buildings_joined.loc[buildings_joined['connected'] == 1]

    # do the same for the network array
    network_df = pd.DataFrame(columns=['idx', 'xs', 'ys', 'xe', 'ye', 'node_start', 'node_end',
                                       'directed', 'length', 'enabled'], data=network)
    network_geometry = [LineString([(arc[1], arc[2]), (arc[3], arc[4])]) for arc in network]
    network_gdf = gpd.GeoDataFrame(network_df, crs=EPSG102022, geometry=network_geometry)
    network_wgs84 = network_gdf.to_crs(epsg=4326)
    network_wgs84 = network_wgs84.loc[network_wgs84['enabled'] == 1]

    return network_wgs84, buildings_joined


def gdf_to_geojson(gdf, property_cols=[]):
    geoJson = {'type': 'FeatureCollection',
           'features': []}    

    for idx, row in gdf.iterrows():
        geoJson['features'].append({
            'type': 'Feature',
            'geometry': get_geometry(row['geometry']),
            'properties': get_properties(row, property_cols)
        })

    return geoJson


def get_geometry(geometry):
    geom_dict = {}
    
    if isinstance(geometry, LineString):
        geom_dict['type'] = 'LineString'
        geom_dict['coordinates'] = list(geometry.coords)

    elif isinstance(geometry, Polygon):
        geom_dict['type'] = 'Polygon'
        geom_dict['coordinates'] = [list(geometry.exterior.coords)]
    
    elif isinstance(geometry, MultiPolygon):
        if len(geometry.geoms) > 1:
            # should handle true multipolygons somehow
            pass
        
        geom_dict['type'] = 'Polygon'
        geom_dict['coordinates'] = [list(geometry.geoms[0].exterior.coords)]
        
    return geom_dict


def get_properties(row, property_cols):
    properties = {}
    
    for col in property_cols:
        properties[col] = row[col]
        
    return properties
