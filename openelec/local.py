# local.py
#!python3

"""
local module for openelec
Tool designed to take a small village and estimate the optimum connections, based on a PV installation location and economic data.

GPL-3.0 (c) Chris Arderne
"""

import json
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString
from math import sqrt
import geopandas as gpd

from openelec import util
from openelec import io
from openelec import network

class LocalModel:
    """
    # model
    # summary
    # spatialise
    # post_process
    # ...
    """

    def __init__(self, data, min_area=20):
        """
        Initialise LocalModel object and read input data.

        Parameters
        ----------
        data : str, Path or GeoJSON-like
            Fiona-readable file or GeoJSON representation of polygon features.
        min_area : int, optional (default 20.)
            Area in m2, below which features will be excluded.
        """

        self.data = data
        self.targets = io.read_data(data=self.data,
                                    sort_by='area')

        self.targets = baseline(self.targets, min_area=min_area)
        self.x_mean = self.targets.geometry.centroid.x.mean()
        self.y_mean = self.targets.geometry.centroid.y.mean()
    
    
    def connect_targets(self, origin=None):
        """
        Create an MST connecting the target features.

        Parameters
        ----------
        origin : tuple of two floats
            Tuple of format (latitude, longitude) of origin point
            (such as a generator) if desired. If not supplied, the 
            largest target building is used instead,
        """

        columns = ['x', 'y', 'area', 'marg_dist', 'conn']
        self.origin = origin
        self.network, self.nodes = network.create_network(targets=self.targets,
                                                          columns=columns,
                                                          directed=True,
                                                          origin=self.origin)


    def save_to_path(self, path):
        """
        Save the resultant network and buildings to GeoJSON files.
        spatialise() must have been run before.

        Parameters
        ---------
        path : str, Path
            Path to a directory to create GeoJSON files.
            Will be created if needed, will not prompt on overwrite.
        """

        io.save_to_path(path, network_out=self.network_gdf, buildings_out=self.buildings_gdf)


    def spatialise(self):
        """
        Convert all model output to GeoDataFrames and GeoJSON objects.
        """

        self.network_gdf = io.spatialise(self.network, type='line')
        
        # TODO this should happen automatically somewhere else
        self.network_gdf = self.network_gdf.loc[self.network_gdf['enabled'] == 1]
        self.network_gdf = self.network_gdf.drop(labels='existing', axis='columns')

        self.network_geojson = io.geojsonify(self.network_gdf)

        self.buildings_gdf = io.merge_geometry(self.nodes, self.targets,
                                               columns=['conn', 'marg_dist'])
        self.buildings_geojson = io.geojsonify(self.buildings_gdf,
                                               property_cols=['area', 'conn'])


    def parameters(self, demand, tariff, gen_cost, cost_wire, cost_connection,
                   opex_ratio, years, discount_rate):
        """
        Set up model parameters.

        Parameters
        ----------
        demand: int
            Demand in kWh/person/month.
        tariff: float
            Tariff to be charged in USD/kWh.
        gen_cost: int
            Generator cost in USD/kW.
        cost_wire: int
            Wire cost in USD/m.
        cost_connection: int
            Cost per household connection in USD.
        opex_ratio: float
            Annual OPEX as a percentage of CAPEX (range 0 -1).
        years: int
            Project duration in years.
        discount_rate: float
            Discount rate to be used for NPV calculation (range 0-1).
        """

        self.demand = float(demand)
        self.tariff = float(tariff)
        self.gen_cost = float(gen_cost)
        self.cost_wire = float(cost_wire)
        self.cost_connection = float(cost_connection)
        self.opex_ratio = float(opex_ratio)
        self.years = int(years)
        self.discount_rate = float(discount_rate)

        # be flexible to inputs as percentage or decimals
        if self.opex_ratio >= 1:
            self.opex_ratio /= 100
        if self.discount_rate >= 1:
            self.discount_rate /= 100

        self.num_people_per_m2 = 0.15  # bit of a guess that there are 4 people in 40m2 house
        self.demand_per_person_kw_peak = self.demand / (4*30)  # 130 is based on MTF numbers, should use a real demand curve
        self.gen_size_kw = self.targets['area'].sum() * self.num_people_per_m2 * self.demand_per_person_kw_peak
        self.cost_gen = self.gen_size_kw * self.gen_cost


    def model(self, target_coverage=None):
        """
        Run the model with the given economic parameters and 
        return the processed network and nodes.

        Parameters
        ----------
        target_coverage: float, optional
            If provided, model will aim to achieve this level of population coverage,
            rather than optimising on NPV.
        """

        # cut arcs one by one, see which cut is the *most* profitable, and then take that network and repeat the process
        # annual income should be specified by the nodes

        # Then we start with the complete network, and try 'deleting' each arc.
        # Whichever deletion is the most profitable, we make it permanent and
        # repeat the process with the new configuration.
        # This continues until there are no more increases in profitability to be had.

        best_npv = None
        total_arcs = len(self.network)

        while True:
            found = False
            for arc in self.network:
                # use a recursive function to calculate profitability of network
                # this should all be done in a temporary network variable
                # and indicate that this arc should be treated as if disabled
                self.network, self.nodes, cost, income_per_month = calculate_profit(self.network, self.nodes,
                    index=0, disabled_arc_index=arc['i'],
                    cost=0, income_per_month=0,
                    cost_wire=self.cost_wire,
                    cost_connection=self.cost_connection,
                    num_people_per_m2=self.num_people_per_m2,
                    demand=self.demand,
                    tariff=self.tariff)

                capex = self.cost_gen + cost
                opex = (self.opex_ratio * capex)
                income = income_per_month * 12
                
                flows = np.ones(self.years) * (income - opex)
                flows[0] = -capex
                npv = np.npv(self.discount_rate, flows)

                #print(cost)
                
                # check if this is the most profitable yet
                # TODO this arc[enabled] check is new
                if best_npv == None or (npv > best_npv): # and arc['enabled'] == 1):
                    found = True
                    best_npv = npv
                    best_npv_index = arc['i']

            if found:
                # disable that arc
                self.network[best_npv_index]['enabled'] = 0

            # now repeat the above steps for the whole network again
            # until we go through without finding a more profitable setup than what we already have
            else:
                if target_coverage == None:
                    break
                else:
                    actual_coverage = len([arc for arc in self.network if arc['enabled'] == 1])/total_arcs
                    if actual_coverage <= target_coverage:
                        break

        self.network, self.nodes = connect_houses(self.network, self.nodes, 0)
        self.network, self.nodes = stranded_arcs(self.network, self.nodes)


    def summary(self):
        """
        And calculate some quick summary numbers for the village.
        Needs to be inside model() if I don't want to pass all the
        parameters around again.


        Returns
        -------
        results: dict
            Dict of summary results.
        """

        count_nodes = 0
        income_per_month = 0
        gen_size_kw = 0
        for node in self.nodes:
            if node['conn'] == 1:
                count_nodes += 1
                income_per_month += node['area'] * self.num_people_per_m2 * self.demand * self.tariff
                gen_size_kw += node['area'] * self.num_people_per_m2 * self.demand_per_person_kw_peak
        
        if self.origin:
            count_nodes -= 1  # so we don't count the generator

        total_length = 0.0
        for arc in self.network:
            if arc['enabled'] == 1:
                total_length += arc['len']

        capex = gen_size_kw * self.gen_cost + self.cost_connection * count_nodes + self.cost_wire * total_length
        opex = (self.opex_ratio * capex)
        income = income_per_month * 12

        flows = np.ones(self.years) * (income - opex)
        flows[0] = -capex
        npv = np.npv(self.discount_rate, flows)

        self.results = {'connected': count_nodes,
                'gen-size': int(gen_size_kw),
                'line-length': int(total_length),
                'capex': int(capex),
                'opex': int(opex),
                'income': int(income),
                'npv': int(npv)}

        return self.results


def calculate_profit(network, nodes, index, disabled_arc_index, cost, income_per_month,
                     cost_wire, cost_connection, num_people_per_m2, demand, tariff):
    """
    Here we recurse through the network and calculate profit, 
    starting with all arcs that connect to the index node,
    and get the end-nodes for those arcs
    calculate profit on those nodes, and then recurse!
    disabled_arc should be treated as if disabled

    Parameters
    ----------
    network, nodes : list of dicts
        Current state of both.
    index : int
        Current index.
    disabled_arc_index : int
        Arc that is currently disabled.
    cost etc : all other parameters
    """
    
    # first calculate the profitability of thise node?
    cost += cost_wire * nodes[index]['marg_dist'] + cost_connection
    income_per_month += nodes[index]['area'] * num_people_per_m2 * demand * tariff
    
    connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
    for arc in connected_arcs:
        if arc['enabled'] == 1 and arc['i'] != disabled_arc_index and arc['ns'] == index:
            network, nodes, cost, income_per_month = calculate_profit(network, nodes,
                index=arc['ne'], disabled_arc_index=disabled_arc_index,
                cost=cost, income_per_month=income_per_month,
                cost_wire=cost_wire,
                cost_connection=cost_connection,
                num_people_per_m2=num_people_per_m2,
                demand=demand,
                tariff=tariff)
            
    return network, nodes, cost, income_per_month


def baseline(targets, min_area=20):
    """
    Filter on population and assign whether currently electrified.

    Parameters
    ----------
    targets: GeoDataFrame
        Loaded targets.
    min_area : int, optional (default 20.)
        Minimum target area in m2.

    Returns
    -------
    targets: GeoDataFrame
        The processed targets.
    """
    
    min_area = float(min_area)
    targets = targets.loc[targets['area'] > min_area]

    targets = targets.assign(marg_dist=0, conn=0)

    return targets

                                
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
