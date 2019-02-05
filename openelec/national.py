# national.py
#!python3

"""
natioanl module for openelec

GPL-3.0 (c) Chris Arderne
"""

from math import sqrt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path

from openelec import util


class NationalModel:
    def __init__(self):
        """

        """
        pass

    # io.read_data
    # baseline
    # create
    # model
    # spatialise
    # post_process
    # ...


def baseline(targets, grid_dist_connected=1000, minimum_pop=200, min_ntl_connected=50):
    """
    Filter on population and assign whether currently electrified.

    Parameters
    ----------
    targets: GeoDataFrame
        Loaded targets.
    grid_dist_connected: int, optional (default 1000.)
        The distance in m from the grid to consider villages already connected.
    minimum_pop: int, optional (default 200.)
        Exclude from analysis villages with less than this pop.
    min_ntl_connected: int, optional (default 50.)
        Minimum NTL (night time lights value) to consider a village already connected.
        Range 0-255.

    Returns
    -------
    targets: GeoDataFrame
        The processed targets.
    """
    
    targets['conn_start'] = 0
    targets.loc[targets['grid'] <= grid_dist_connected, 'conn_start'] = 1
    targets.loc[targets['ntl'] <= min_ntl_connected, 'conn_start'] = 0
    targets = targets.loc[targets['pop'] > minimum_pop]

    targets['conn_end'] = targets['conn_start']
    targets['og_cost'] = 0

    return targets


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


def post_process(network, targets):
    """
    Basic filtering and processing on results.
    Targets 'type' can be one of:
     - orig: was always connected
     - new: new grid connection
     - og: new off-grid connection
     TODO Add no connection type.

    Parameters
    ----------
    network, targets : GeoDataFrame
        Output from model.

    Returns
    -------
    network, targets : GeoDataFrame
        Processed results.
    """

    # Only keep new network lines created by model
    # TODO this should happen automatically somewhere else
    network = network.loc[network['existing'] == 0].loc[network['enabled'] == 1]

    # Assign target type based on model results
    targets['type'] = ''
    targets.loc[(targets['conn_end'] == 1) & (targets['conn_start'] == 1), 'type'] = 'orig'
    targets.loc[(targets['conn_end'] == 1) & (targets['conn_start'] == 0), 'type'] = 'new'
    targets.loc[targets['conn_end'] == 0, 'type'] = 'og'

    return network, targets


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
