# util.py
#!python3

"""
Helper functions for models.
"""

from math import pi, ceil, sqrt

import numpy as np


def connect_houses(network, nodes, index):
    """
    Then we disconnect all the houses that are no longer served by active arcs,
    and prune any stranded arcs that remained on un-connected paths.
    now we need to tell the houses that aren't connected, that they aren't connected (or vice-versa)
    recurse from the starting point and ID connected houses as connected?

    Start from base, follow connection (similar to calculate_profit) and swith node[6] to 1 wherever connected
    and only follow the paths of connected houses
    """
    
    # this node is connected
    nodes[index]['conn'] = 1
    
    connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
    for arc in connected_arcs:
        if arc['enabled'] == 1 and arc['ns'] == index:
            connect_houses(network, nodes, arc['ne'])

    return network, nodes
            
    
def stranded_arcs(network, nodes):
    """
    And do the same for the stranded arcs
    """

    for node in nodes:
        if node['conn'] == 0:
            connected_arcs = [network[arc_index] for arc_index in node['arcs']]
            for arc in connected_arcs:
                arc['enabled'] = 0

    return network, nodes


def calc_coverage(weight, pop, conn, pop_tot, target_access, accuracy=0.01, increment=0.1, max_coverage=0.8):
    """
    
    """
    
    coverage = np.zeros_like(weight)
    error = 1
    add = 0.0
    loop = 0

    while error > accuracy:
        count = 0
        for i in range(len(coverage)):
            if conn[i]:
                count += 1
                if loop == 0:
                    coverage[i] = weight[i]
                else:
                    coverage[i] += add
                    coverage[i] = min(coverage[i], max_coverage)

                access = (coverage * pop * conn).sum() / pop_tot
                error = abs(access - target_access)
                if error <= accuracy:
                    #print(f'Access rate error: {100*error:.0f}%')
                    break
        
        loop += 1        
        add += increment

    return coverage


def assign_coverage(targets, access_rate):
    """
    
    """
    
    targets = targets.copy()
    # total population for calculating access target
    pop_tot = targets['pop'].sum()

    # calculate a 'weight' for each cell from it's brightness per person
    # normalized to a scale of 0-1 and limited to second highest value
    targets['weight'] = targets['ntl'] / targets['pop']
    targets['weight'] = targets['weight'] / targets['weight'].max()
    second_highest = targets['weight'].nlargest(2).to_numpy()[1]
    targets.loc[targets['weight'] > second_highest, 'weight'] = second_highest

    by_weight = targets.sort_values(by='weight', ascending=False)
    weight = by_weight['weight'].to_numpy(copy=True)
    pop = by_weight['pop'].to_numpy(copy=True)
    conn = by_weight['conn_start'].to_numpy(copy=True)
    
    coverage = calc_coverage(weight, pop, conn, pop_tot=pop_tot, target_access=access_rate)
    by_weight['coverage'] = coverage
    targets = by_weight.sort_values(by='pop', ascending=False)
    
    return targets['coverage']


def calc_lv(people, demand, people_per_hh, area):
    """
    Calculate LV cost parameters for the given parameters.
    Everything is in m and m2.

    Parameters
    ----------
    """

    hours_per_year = 8760
    max_transformer_kVA = 50
    base_to_peak = 0.85                # for the sizing of needed capacity
    power_factor = 0.9                 # From (1)
    
    nodes = people / people_per_hh
    
    average_load = people * demand * 12 / hours_per_year
    peak_kVA = average_load / base_to_peak / power_factor
    
    transformers = ceil(peak_kVA/max_transformer_kVA)
    if transformers <= 0:
        transformers = 1

    transformer_radius = sqrt((area / transformers) / pi)
    cluster_radius = sqrt(area / pi)
    
    mv_len = 2/3 * cluster_radius *  transformers
    lv_len = 2/3 * transformer_radius * nodes
    
    return mv_len, lv_len, transformers
