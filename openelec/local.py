# local.py
#!python3

"""
local module for openelec
Tool designed to take a small village and estimate the optimum connections, based on a PV installation location and economic data.

GPL-3.0 (c) Chris Arderne
"""

import numpy as np

from .model import Model
from . import io
from . import network
from . import util


class LocalModel(Model):
    """
    Inherits from Model.
    Goal is to fully merge NationalModel and LocalModel, as they share lots of functionality.

    This class provides most of the functionality for using openelec at the local level.
    """    

    def baseline(self, min_area=20):
        """
        Filter on population and assign whether currently electrified.

        Parameters
        ----------
        targets: GeoDataFrame
            Loaded targets.
        min_area : int, optional (default 20.)
            Minimum target area in m2.
        """
        
        min_area = float(min_area)
        self.targets = self.targets.loc[self.targets['area'] > min_area]
        self.targets = self.targets.assign(marg_dist=0, conn=0)

    
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
        self.network, self.nodes = network.create_network(self.targets,
            columns=columns,
            directed=True,
            origin=self.origin)


    def spatialise(self):
        """
        Convert all model output to GeoDataFrames.
        """

        self.network_out = io.spatialise(self.network, type='line')
        
        # TODO this should happen automatically somewhere else
        self.network_out = self.network_out.loc[self.network_out['enabled'] == 1]
        self.network_out = self.network_out.drop(labels='existing', axis='columns')

        self.targets_out = io.merge_geometry(self.nodes, self.targets,
                                               columns=['conn', 'marg_dist'])   
    

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

        cut arcs one by one, see which cut is the *most* profitable, and then take that network and repeat the process
        annual income should be specified by the nodes

        Then we start with the complete network, and try 'deleting' each arc.
        Whichever deletion is the most profitable, we make it permanent and
        repeat the process with the new configuration.
        This continues until there are no more increases in profitability to be had.

        Parameters
        ----------
        target_coverage: float, optional
            If provided, model will aim to achieve this level of population coverage,
            rather than optimising on NPV.
        """

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

        self.network, self.nodes = util.connect_houses(self.network, self.nodes, 0)
        self.network, self.nodes = util.stranded_arcs(self.network, self.nodes)


    def summary(self):
        """
        Calculate some quick summary numbers for the village.

        Returns
        -------
        results : dict
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

                                

