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

from openelec.model import Model
from openelec import util
from openelec import io
from openelec import network


class NationalModel(Model):
    """

    """


    def baseline(self, grid_dist_connected=1000, minimum_pop=200, min_ntl_connected=50):
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
        """
        
        self.targets = self.targets.assign(conn_start=0, og_cost=0)
        self.targets.loc[self.targets['grid'] <= grid_dist_connected, 'conn_start'] = 1
        self.targets.loc[self.targets['ntl'] <= min_ntl_connected, 'conn_start'] = 0
        self.targets = self.targets.loc[self.targets['pop'] > minimum_pop]

        self.targets['conn_end'] = self.targets['conn_start']


    def connect_targets(self):
        """
        Create an MST connecting the target features.
        """

        columns = ['x', 'y', 'area', 'pop', 'conn_start', 'conn_end', 'og_cost']
        self.network, self.nodes = network.create_network(self.targets, existing_network=True, 
            columns=columns)


    def spatialise(self):
        """
        Basic filtering and processing on results.
        Targets 'type' can be one of:
        - orig: was always connected
        - new: new grid connection
        - og: new off-grid connection
        TODO Add no-connection type.

        Parameters
        ----------
        network, targets : GeoDataFrame
            Output from model.
        """

        self.network_out = io.spatialise(self.network, type='line')

        # Only keep new network lines created by model
        # TODO this should happen automatically somewhere else
        self.network_out = self.network_out.loc[self.network_out['existing'] == 0].loc[self.network_out['enabled'] == 1]

        self.targets_out = io.merge_geometry(self.nodes, self.targets,
                                             columns=['conn_end', 'og_cost'])

        # Assign target type based on model results
        self.targets_out['type'] = ''
        self.targets_out.loc[(self.targets_out['conn_end'] == 1) & (self.targets_out['conn_start'] == 1), 'type'] = 'orig'
        self.targets_out.loc[(self.targets_out['conn_end'] == 1) & (self.targets_out['conn_start'] == 0), 'type'] = 'new'
        self.targets_out.loc[self.targets_out['conn_end'] == 0, 'type'] = 'og'


    def parameters(self, demand, mg_gen_cost, mg_dist_cost, grid_mv_cost, grid_lv_cost, urban_elec):
        """
        Set up model parameters
        """

        self.demand = float(demand)
        self.demand_per_person_kw_peak = self.demand / (4*30)  # 130 4hours/day*30days/month based on MTF numbers, should use a real demand curve
        self.mg_gen_cost = float(mg_gen_cost)
        self.mg_dist_cost = float(mg_dist_cost)
        self.grid_mv_cost = float(grid_mv_cost)
        self.grid_lv_cost = float(grid_lv_cost)

        self.urban_elec = float(urban_elec)
        # be flexible to inputs as percentage or decimals
        if self.urban_elec >= 1:
            self.urban_elec /= 100


    def model(self):
        """
        Run the national planning model with the provided parameters.

        Then we're ready to calculate the optimum grid extension.
        This is done by expanding out from each already connected node,
        finding the optimum connection of nearby nodes.
        This is then compared to the off-grid cost and if better,
        these nodes are marked as connected.
        Then the loop continues until no new connections are found.
        """

        # First calcaulte the off-grid cost for each unconnected settlement
        for node in self.nodes:
            if node['conn_start'] == 0:
                node['og_cost'] = node['pop']*self.demand_per_person_kw_peak*self.mg_gen_cost + node['area']*self.mg_dist_cost

        # keep looping until no further connections are added
        while True:
            to_be_connected = []
            
            for node in self.nodes:
                # only start searches from currently connected nodes
                if node['conn_end'] == 1:
                    
                    connected_arcs = [self.network[arc_index] for arc_index in node['arcs']]
                    for arc in connected_arcs:
                        if arc['enabled'] == 0:
                            goto = 'ne' if arc['ns'] == node['i'] else 'ns'
                            
                            # function call a bit of a mess with all the c_ and b_ values
                            self.network, self.nodes, b_length, b_pop, b_nodes, b_arcs = find_best(
                                self.network, self.nodes, arc[goto], arc['i'], 0, 1e-9, [], [], 0, 1e-9, [], [])                

                            # calculate the mg and grid costs of the resultant configuration
                            best_nodes = [self.nodes[i] for i in b_nodes]
                            best_arcs = [self.network[i] for i in b_arcs]
                            mg_cost = sum([node['og_cost'] for node in best_nodes])
                            grid_cost = (self.grid_mv_cost * sum(arc['len'] for arc in best_arcs) + 
                                        self.grid_lv_cost * sum([node['area'] for node in best_nodes]))

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
                        self.nodes[node]['conn_end'] = 1
                    for arc in item[2]:
                        self.network[arc]['enabled'] = 1
            
            # exit the loop once nothing is added
            else:
                break

    def summary(self):
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

        new = self.targets_out.loc[self.targets_out['type'] == 'new']
        og = self.targets_out.loc[self.targets_out['type'] == 'og']
        orig = self.targets_out.loc[self.targets_out['type'] == 'orig']
        cost = og['og_cost'].sum() + self.grid_mv_cost * self.network_out['len'].sum() + self.grid_lv_cost * new['area'].sum()

        # tags must match those in the config file
        self.results = {
            'new-conn': len(new),
            'new-og': len(og),
            'tot-cost': cost,
            'model-pop': self.targets_out['pop'].sum(),
            'orig-conn-pop': orig['pop'].sum() * self.urban_elec,
            'new-conn-pop': new['pop'].sum(),
            'new-og-pop': og['pop'].sum()
        }

        return self.results


def find_best(network, nodes, index, prev_arc, b_pop, b_length, b_nodes, b_arcs, c_pop, c_length, c_nodes, c_arcs):
    """
    This function recurses through the network, dragging a current c_ values along with it.
    These aren't returned, so are left untouched by aborted side-branch explorations.
    The best b_ values are returned, and are updated whenever a better configuration is found.
    Thus these will remmber the best solution including all side meanders.
    """

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
                network, nodes, b_pop, b_length, b_nodes, b_arcs = find_best(
                    network, nodes, arc[goto], arc['i'], b_pop, b_length, b_nodes, b_arcs, c_pop, c_length, c_nodes, c_arcs)
                
    return network, nodes, b_pop, b_length, b_nodes, b_arcs
