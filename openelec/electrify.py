"""
electrify.py
"""

from math import sqrt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path

from openelec import mgo


def country_centroid(file_path):
    """
    Get the centroid of any given file path.

    Parameters
    ----------
    file_path: string
        File path to a file that GeoPandas can understand.

    Returns
    -------
    lat, lng: tuple of floats
        Latitude and longitude in WGS84 decimal degree coordinates.
    """

    gdf = gpd.read_file(file_path)
    lng = gdf.geometry.centroid.x.mean()
    lat = gdf.geometry.centroid.y.mean()

    return lat, lng


def load_clusters(clusters_file, grid_dist_connected=1000, minimum_pop=200):
    """

    """
    # Read in the clusters file, convert to desired CRS (ostensibly better for distances) and convert to points, filter on population along the way
    clusters = gpd.read_file(str(clusters_file))
    # This is the Africa Albers Equal Area Conic EPSG: 102022
    epsg102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
    clusters = clusters.to_crs(epsg102022)

    clusters['conn_start'] = 0
    clusters.loc[clusters['grid_dist'] <= grid_dist_connected, 'conn_start'] = 1
    clusters = clusters.loc[clusters['pop'] > minimum_pop]
    clusters = clusters.sort_values('pop', ascending=False)  # so that biggest (and thus connected) city gets index=0
    clusters = clusters.reset_index().drop(columns=['index'])

    return clusters


def find_score(clusters, min_grid_dist=1000):
    """

    """
    clusters = clusters.loc[clusters['grid_dist'] > min_grid_dist]

    def get_score(row):
        grid_score = 0
        if row['grid_dist'] > 5000:
            grid_score = 1
        elif row['grid_dist'] > 10000:
            grid_score = 2

        pop_score = 0
        if row['pop'] > 500:
            pop_score = 1
        elif row['pop'] > 1000:
            pop_score = 2
        elif row['pop'] > 2000:
            pop_score = 3

        return grid_score + pop_score

    clusters['score'] = clusters.apply(get_score, axis=1)
    clusters = clusters.to_crs(epsg=4326)

    summary = {
        'num-clusters': len(clusters)
    }

    return clusters, summary


def create_network(clusters):
    """
    We then take all the clusters and calculate the optimum network that connects them all together.
    The ML model returns T_x and T_y containing the start and end points of each new arc created.
    """

    clusters_points = clusters.copy()
    clusters_points.geometry = clusters_points['geometry'].centroid
    clusters_points['X'] = clusters_points.geometry.x
    clusters_points['Y'] = clusters_points.geometry.y

    df = pd.DataFrame(clusters_points)
    points = df[['X', 'Y']].as_matrix()

    T_x, T_y = mgo.get_spanning_tree(points)

    # This point and line data is then copied into two arrays, called network and nodes,
    # containing the lines and clusters, respectively. Each element represents a single cluster or joining arc,
    # and has data within describing the coordinates and more.

    df['conn_end'] = df['conn_start']
    df['off_grid_cost'] = 0

    nodes_list = df[['X', 'Y', 'area', 'pop', 'conn_start', 'conn_end', 'off_grid_cost']].reset_index().values.astype(int).tolist()
    nodes = []
    # add an empty list at position 8 for connected arc indices
    for n in nodes_list:
        nodes.append({'i': n[0], 'x': n[1], 'y': n[2], 'area': n[3], 'pop': n[4], 'conn_start': n[5], 'conn_end': n[6], 'og_cost': n[7], 'arcs': []})

    counter = 0
    network = []
    for xs, ys, xe, ye in zip(T_x[0], T_y[0], T_x[1], T_y[1]):
        xs = int(xs)
        ys = int(ys)
        xe = int(xe)
        ye = int(ye)
        length = int(sqrt((xe - xs)**2 + (ye - ys)**2))
        network.append({'i': counter, 'xs': xs, 'ys': ys, 'xe': xe, 'ye': ye, 'ns': None, 'ne': None, 'existing': 1, 'len': length, 'enabled': 1})
        counter += 1


    network, nodes = connect_network(network, nodes, 0)

    # for every node, add references to every arc that connects to it
    for arc in network:
        nodes[arc['ns']]['arcs'].append(arc['i'])
        nodes[arc['ne']]['arcs'].append(arc['i'])
        
    # set which arcs don't already exist (and the remainder do!)
    for node in nodes:
        if node['conn_start'] == 0:
            connected_arcs = [network[arc_index] for arc_index in node['arcs']]
            for arc in connected_arcs:
                arc['existing'] = 0
                arc['enabled'] = 0 

    return network, nodes


def connect_network(network, nodes, index):
    """
    Then we need to tell each arc which nodes it is connected to, and likewise for each node
    Each arc connects two nodes, each node can have 1+ arcs connected to it
    """

    cur_node = nodes[index]
    for arc in network:
        found = 0
        if arc['ns'] == None and arc['ne'] == None:  # if this arc has no connected nodes
            if (arc['xs'] == cur_node['x'] and arc['ys'] == cur_node['y']):  # if the xs and ys match a node
                found = 'xe'  # point towards position 3 (xe) for the next node
            if (arc['xe'] == cur_node['x'] and arc['ye'] == cur_node['y']):  # if the xe and ye match a node
                found = 'xs'  # point towards position 1 (xs) for the next node

            if found:
                arc['ns'] = cur_node['i'] # tell this arc that this node is its starting point
            
                for node in nodes:
                    if node['i'] != cur_node['i']:  # make sure we look at hte other end of the arc
                        if node['x'] == arc[found] and node['y'] == arc['ye' if found == 'xe' else 'ys']:
                            arc['ne'] = node['i'] # tell this arc that this node is its ending point                  
                            network, nodes = connect_network(network, nodes, node['i']) # and investigate downstream
                            break
    
    return network, nodes


def run_model(network, nodes, demand_per_person_kw_peak, mg_gen_cost_per_kw, mg_cost_per_m2, cost_wire_per_m, grid_cost_per_m2):
    """

    """

    # First calcaulte the off-grid cost for each unconnected settlement
    for node in nodes:
        if node['conn_start'] == 0:
            node['og_cost'] = node['pop']*demand_per_person_kw_peak*mg_gen_cost_per_kw + node['area']*mg_cost_per_m2


    # Then we're ready to calculate the optimum grid extension.
    # This is done by expanding out from each already connected node,
    # finding the optimum connection of nearby nodes.
    # This is then compared to the off-grid cost and if better,
    # these nodes are marked as connected.
    # Then the loop continues until no new connections are found.

    # This function recurses through the network, dragging a current c_ values along with it.
    # These aren't returned, so are left untouched by aborted side-branch explorations.
    # The best b_ values are returned, and are updated whenever a better configuration is found.
    # Thus these will remmber the best solution including all side meanders.

    def find_best(nodes, network, index, prev_arc, b_pop, b_length, b_nodes, b_arcs, c_pop, c_length, c_nodes, c_arcs):
        if nodes[index]['conn_end'] == 0:  # don't do anything with already connected nodes
            
            
            c_pop += nodes[index]['pop']
            c_length += network[prev_arc]['len']
            c_nodes = c_nodes[:] + [index]
            c_arcs = c_arcs[:] + [prev_arc]
                  
            if c_pop/c_length > b_pop/b_length:
                b_pop = c_pop
                b_length = c_length
                b_nodes[:] = c_nodes[:]
                b_arcs[:] = c_arcs[:]
        
            connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
            for arc in connected_arcs:
                if arc['enabled'] == 0 and arc['i'] != prev_arc:

                    goto = 'ne' if arc['ns'] == index else 'ns'  # make sure we look at the other end of the arc
                    nodes, network, b_pop, b_length, b_nodes, b_arcs = find_best(
                        nodes, network, arc[goto], arc['i'], b_pop, b_length, b_nodes, b_arcs, c_pop, c_length, c_nodes, c_arcs)
                    
        return nodes, network, b_pop, b_length, b_nodes, b_arcs


    while True:  # keep looping until no further connections are added
        to_be_connected = []
        
        for node in nodes:
            if node['conn_end'] == 1:  # only start searches from currently connected nodes
                
                connected_arcs = [network[arc_index] for arc_index in node['arcs']]
                for arc in connected_arcs:
                    if arc['enabled'] == 0:
                        goto = 'ne' if arc['ns'] == node['i'] else 'ns'
                        
                        # function call a bit of a mess with all the c_ and b_ values
                        nodes, network, b_length, b_pop, b_nodes, b_arcs = find_best(
                            nodes, network, arc[goto], arc['i'], 0, 1e-9, [], [], 0, 1e-9, [], [])                

                        # calculate the mg and grid costs of the resultant configuration
                        best_nodes = [nodes[i] for i in b_nodes]
                        best_arcs = [network[i] for i in b_arcs]
                        mg_cost = sum([node['og_cost'] for node in best_nodes])
                        grid_cost = (cost_wire_per_m * sum(arc['len'] for arc in best_arcs) + 
                                     grid_cost_per_m2 * sum([node['area'] for node in best_nodes]))

                        if grid_cost < mg_cost:
                            # check if any nodes are already in to_be_connected
                            add = True
                            for index, item in enumerate(to_be_connected):
                                if set(b_nodes).intersection(item[1]):
                                    if b_pop/b_length < item[0]:
                                        del to_be_connected[index]
                                    else:
                                        add = False  # if the existing one is better, we don't add the new one
                                    break

                            if add:
                                to_be_connected.append((b_pop/b_length, b_nodes, b_arcs))
            
        # mark all to_be_connected as actually connected
        if len(to_be_connected) >= 1:
            for item in to_be_connected:
                for node in item[1]:
                    nodes[node]['conn_end'] = 1
                for arc in item[2]:
                    network[arc]['enabled'] = 1
        
        else:
            break  # exit the loop once nothing is added

    return network, nodes


def spatialise(network, nodes, clusters):
    """
    And then do a join to get the results back into a polygon shapefile
    """

    # prepare nodes and join with original clusters gdf
    nodes_df = pd.DataFrame(nodes)
    nodes_df = nodes_df[['conn_end', 'og_cost']]
    clusters_joined = clusters.merge(nodes_df, how='left', left_index=True, right_index=True)
    clusters_joined = clusters_joined.to_crs(epsg=4326)

    # do the same for the network array
    network_df = pd.DataFrame(network)
    network_geometry = [LineString([(arc['xs'], arc['ys']), (arc['xe'], arc['ye'])]) for arc in network]
    network_gdf = gpd.GeoDataFrame(network_df, crs=clusters.crs, geometry=network_geometry)
    network_gdf = network_gdf.to_crs(epsg=4326)
    network = network_gdf.loc[network_gdf['existing'] == 0].loc[network_gdf['enabled'] == 1]

    clusters_joined['type'] = ''
    clusters_joined.loc[(clusters_joined['conn_end'] == 1) & (clusters_joined['conn_start'] == 1), 'type'] = 'orig'
    clusters_joined.loc[(clusters_joined['conn_end'] == 1) & (clusters_joined['conn_start'] == 0), 'type'] = 'new'
    clusters_joined.loc[clusters_joined['conn_end'] == 0, 'type'] = 'og'

    return network, clusters_joined


def summary_results(network, clusters, urban_elec, grid_mv_cost, grid_lv_cost):

    urban_elec = float(urban_elec)

    new = clusters.loc[clusters['type'] == 'new']
    og = clusters.loc[clusters['type'] == 'og']
    orig = clusters.loc[clusters['type'] == 'orig']
    cost = og['og_cost'].sum() + grid_mv_cost * network['len'].sum() + grid_lv_cost * new['area'].sum()

    # tags must match those in the config file
    results = {
        'new-conn': len(new),
        'new-og': len(og),
        'tot-cost': cost,
        'model-pop': clusters['pop'].sum(),
        'orig-conn-pop': orig['pop'].sum() * urban_elec,
        'new-conn-pop': new['pop'].sum(),
        'new-og-pop': og['pop'].sum()
    }

    return results