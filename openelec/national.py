"""
natioanl module for openelec

(c) Chris Arderne
"""

from math import sqrt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path

from openelec import util, clustering

import rasterio

# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
MOLL = {'proj': 'moll', 'lon_0': 0, 'x_0': 0, 'y_0': 0, 'ellps': 'WGS84', 'units': 'm', 'no_defs': True}

def load_clusters(clusters_file, grid_dist_connected=1000, minimum_pop=200, min_ntl_connected=50,
                  geojson=None, ghs_in=None):
    """
    Read in the specified clusters file, project, filter on population
    and assign whether currently electrified.

    Parameters
    ----------
    clusters_file: file path
        A geospatial clusters file to be loaded, should be created with clustering module.
    grid_dist_connected: int, optional
        The distance in m from the grid to consider villages already connected.
    minimum_pop: int, optional
        Exclude from analysis villages with less than this pop.
    min_ntl_connected: int, optional
        Minimum NTL (night time lights value) to consider a village already connected.
        Range 0-255.

    Returns
    -------
    clusters: GeoDataFrame
        The processed clusters.
    """
    # Read in the clusters file, convert to desired CRS (ostensibly better for distances) and convert to points, filter on population along the way
    clusters = gpd.read_file(clusters_file)
    clusters = clusters.to_crs(EPSG102022)

    ### ADDED FOR POSTGIS TEST
    ghs = rasterio.open(ghs_in)
    shape = ghs.read(1).shape
    affine = ghs.transform
    crs = MOLL

    grid = gpd.GeoDataFrame.from_features(geojson, crs={'init': 'epsg:4326'})

    clusters = clustering.add_vector_layer(clusters=clusters, vector=grid, operation='distance', col_name='grid',
                                                shape=shape, affine=affine, raster_crs=crs)
    clusters = clustering.fix_column(clusters, 'grid', factor=1/1000)
    ### END ADDED FOR POSTGIS TEST

    # basic filtering for planning
    clusters['conn_start'] = 0
    clusters.loc[clusters['grid'] <= grid_dist_connected, 'conn_start'] = 1
    clusters.loc[clusters['ntl'] <= min_ntl_connected, 'conn_start'] = 0
    clusters = clusters.loc[clusters['pop'] > minimum_pop]

    clusters = clusters.sort_values('pop', ascending=False)  # so that biggest (and thus connected) city gets index=0
    clusters = clusters.reset_index().drop(columns=['index'])

    return clusters


def create_network(clusters):
    """
    We then take all the clusters and calculate the optimum network that connects them all together.
    We use this to create a graph network of and nodes and arcs representing the clusters and connections.

    Parameters
    ----------
    clusters: GeoDataFrame
        The prepared clusters.
    
    Returns
    -------
    network: list of dicts
        The network arcs.
    nodes: list of dicts
        The network nodes.
    """

    clusters_points = clusters.copy()
    clusters_points.geometry = clusters_points['geometry'].centroid
    clusters_points['X'] = clusters_points.geometry.x
    clusters_points['Y'] = clusters_points.geometry.y

    # This point and line data is then copied into two arrays, called network and nodes,
    # containing the lines and clusters, respectively. Each element represents a single cluster or joining arc,
    # and has data within describing the coordinates and more.

    clusters_points['conn_end'] = clusters_points['conn_start']
    clusters_points['off_grid_cost'] = 0

    nodes_list = clusters_points[['X', 'Y', 'area', 'pop', 'conn_start', 'conn_end', 'off_grid_cost']].reset_index().values.astype(int).tolist()
    nodes = []
    for n in nodes_list:
        nodes.append({'i': n[0], 'x': n[1], 'y': n[2], 'area': n[3], 'pop': n[4], 'conn_start': n[5], 'conn_end': n[6], 'og_cost': n[7], 'arcs': []})

    mst_points = clusters_points[['X', 'Y']].values
    start_points, end_points, nodes_connected = util.spanning_tree(mst_points, approximate=True)

    counter = 0
    network = []
    for s, e, n in zip(start_points, end_points, nodes_connected):
        xs = int(s[0])
        ys = int(s[1])
        xe = int(e[0])
        ye = int(e[1])
        length = int(sqrt((xe - xs)**2 + (ye - ys)**2))

        ns = n[0]
        ne = n[1]

        nodes[ns]['arcs'].append(counter)
        nodes[ne]['arcs'].append(counter)

        network.append({'i': counter, 'xs': xs, 'ys': ys, 'xe': xe, 'ye': ye, 'ns': ns, 'ne': ne, 'existing': 1, 'len': length, 'enabled': 1})
        counter += 1
        
    # set which arcs don't already exist (and the remainder do!)
    for node in nodes:
        if node['conn_start'] == 0:
            connected_arcs = [network[arc_index] for arc_index in node['arcs']]
            for arc in connected_arcs:
                arc['existing'] = 0
                arc['enabled'] = 0

    return network, nodes


def model(network, nodes, demand_per_person_kw_peak, mg_gen_cost, mg_dist_cost, grid_mv_cost, grid_lv_cost):
    """
    Run the national planning model with the provided parameters.

    Parameters
    ----------
    network: list of dicts
        The network arcs.
    nodes: list of dicts
        The network nodes.
    demand_per_person_kw_peak: int
        Peak demand per person in kW.
    mg_gen_cost: int
        Mini-grid generator (and extra equipment) cost per kW.
    mg_dist_cost: int
        Mini-grid distribution costs as a function of the village size in m2.
    grid_mv_cost: int
        Grid MV wire cost per m.
    grid_lv_cost: int
        Grid LV costs as a function of the village size in m2.

    Returns
    -------
    network: list of dicts
        The cost-optimised network arcs.
    nodes: list of dicts
        The cost-optimised network nodes.
    """

    # First calcaulte the off-grid cost for each unconnected settlement
    for node in nodes:
        if node['conn_start'] == 0:
            node['og_cost'] = node['pop']*demand_per_person_kw_peak*mg_gen_cost + node['area']*mg_dist_cost

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

        # TODO incorporate GDP and other demand factors into pop
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
                        grid_cost = (grid_mv_cost * sum(arc['len'] for arc in best_arcs) + 
                                     grid_lv_cost * sum([node['area'] for node in best_nodes]))

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
    And then do a join to get the results back into GeoDataFrame geometries.

    Parameters
    ----------
    network: list of dicts
        The optimised network arcs.
    nodes: list of dicts
        The optimised network nodes.
    clusters: GeoDataFrame
        The original clusters to be joined back into.

    Returns
    -------
    network: GeoDataFrame
        The optimised network as a GeoDataFrame.
    clusters: GeoDataFrame
        The optimised clusters as a GeoDataFrame.
    """

    # prepare nodes and join with original clusters gdf
    nodes_df = pd.DataFrame(nodes)
    nodes_df = nodes_df[['conn_end', 'og_cost']]
    clusters = clusters.merge(nodes_df, how='left', left_index=True, right_index=True)
    clusters = clusters.to_crs(epsg=4326)

    # do the same for the network array
    network_df = pd.DataFrame(network)
    network_geometry = [LineString([(arc['xs'], arc['ys']), (arc['xe'], arc['ye'])]) for arc in network]
    network_gdf = gpd.GeoDataFrame(network_df, crs=EPSG102022, geometry=network_geometry)
    network_gdf = network_gdf.to_crs(epsg=4326)
    network = network_gdf.loc[network_gdf['existing'] == 0].loc[network_gdf['enabled'] == 1]

    clusters['type'] = ''
    clusters.loc[(clusters['conn_end'] == 1) & (clusters['conn_start'] == 1), 'type'] = 'orig'
    clusters.loc[(clusters['conn_end'] == 1) & (clusters['conn_start'] == 0), 'type'] = 'new'
    clusters.loc[clusters['conn_end'] == 0, 'type'] = 'og'

    return network, clusters


def summary(network, clusters, urban_elec, grid_mv_cost, grid_lv_cost):
    """
    Calculate some summary results.

    Parameters
    ----------
    network: GeoDataFrame
        Final network object.
    clusters: GeoDataFrame
        Final clusters object.
    urban_elec: int or float
        Rate of urban electrification, either as percentage or ratio.
    grid_mv_cost: int
        As for model()
    grid_lv_cost: int
        As for model()
    """

    urban_elec = float(urban_elec)
    # be flexible to inputs as percentage or decimals
    if urban_elec >= 1:
        urban_elec /= 100

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
