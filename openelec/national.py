# national.py
#!python3

"""
national module for openelec

GPL-3.0 (c) Chris Arderne
"""

import numpy as np
import pandas as pd

from .model import Model
from . import io
from . import network
from . import util


class NationalModel(Model):
    """
    Inherits from Model.
    Goal is to fully merge NationalModel and LocalModel, as they share lots of functionality.

    This class provides most of the functionality for using openelec at the national level.
    """


    def parameters(self,
                   demand,
                   grid_mv_cost, grid_lv_cost, grid_trans_cost, grid_conn_cost, grid_opex_ratio,
                   mg_gen_cost, mg_lv_cost, mg_conn_cost, mg_opex_ratio,
                   actual_pop, pop_growth, access_tot, access_urban,
                   grid_dist_connected=1, minimum_pop=200, min_ntl_connected=0,
                   gdp_growth=0.02, discount_rate=0.08,
                   people_per_hh=4, target_access=1):
        """
        # TODO Allow to only pass whatever parameters are wanted (e.g. for reruns)
        Set up model parameters
        """

        self.demand = float(demand)
        self.demand_per_person_kw_peak = self.demand / (4*30)  # 130 4hours/day*30days/month based on MTF numbers
                                                               # TODO should use a real demand curve
        
        self.people_per_hh = float(people_per_hh)
        self.target_access = float(target_access)  # TODO NOT USED

        self.grid_mv_cost = float(grid_mv_cost)
        self.grid_lv_cost = float(grid_lv_cost)
        self.grid_trans_cost = float(grid_trans_cost)
        self.grid_conn_cost = float(grid_conn_cost)  # conn cost per household
        self.grid_opex_ratio = float(grid_opex_ratio)  # TODO NOT USED

        self.mg_gen_cost = float(mg_gen_cost)
        self.mg_lv_cost = float(mg_lv_cost)
        self.mg_conn_cost = float(mg_conn_cost)
        self.mg_opex_ratio = float(mg_opex_ratio)  # TODO NOT USER

        self.actual_pop = float(actual_pop)  # TODO NOT USED
        self.pop_growth = float(pop_growth)
        self.access_tot = float(access_tot)
        self.access_urban = float(access_urban)
        # be flexible to inputs as percentage or decimals
        if self.access_urban >= 1:
            self.access_urban /= 100
        if self.access_tot >= 1:
            self.access_tot /= 100

        self.grid_dist_connected = grid_dist_connected
        self.minimum_pop = minimum_pop
        self.min_ntl_connected = min_ntl_connected

        self.discount_rate = float(discount_rate)  # TODO NOT USED
        self.gdp_growth = float(gdp_growth)
            

    def dynamic_combine(self):
        """
        Run the dyamic model and combine the results into a single set of GeoDataFrames 
        and a results dict.

        Returns
        -------
        targets, network : GeoDataFrames
            Combined targets and network.
        results : dict
            Dict of results keyed on step number.
        """

        dynamic_model = self.dynamic(demand_factor=5)

        targets, network, results = next(dynamic_model)
        targets['type_1'] = targets['type']
        network['stage'] = 1
        results = {1: results}

        count = 2
        for t, n, r in dynamic_model:
            targets[f'type_{count}'] = t['type']
            n['stage'] = count
            network = pd.concat([network, n], ignore_index=True)
            results[count] = r
            count += 1

        return targets, network, results


    def dynamic(self, steps=4, years_per_step=5, demand_factor=None):
        """
        Run the model dynamically, splitting into a specified number of steps
        with a number of years between each one. Creates an iterator that yields
        results after each step.

        Parameters
        ----------
        steps : int, optional (default 4.)
            Number of steps to use.
        years_per_step : int, optional (default 5.)
            Number of years per step.
        demand_factor : int, optional (default None.)
            If provided, uses this factor in demand calculations.
            If None, uses the MTF levels instead.
        
        Yields
        ------
        targets_out, networks_out : GeoDataFrames
            The next step of targets and network.
        results : dict
            The next step of results.
        """

        self.setup(sort_by='pop')
        self.initial_access()

        for s in range(1, steps+1):

            self.demand_levels(factor=demand_factor)
            self.connect_targets()
            self.model()

            # first remove un-enabled arcs from nodes
            for arc in self.network:
                if arc['enabled'] == 0:
                    for node in self.nodes:
                        if arc['i'] in node['arcs']:
                            node['arcs'].remove(arc['i'])

            # starting from the ends, new grid is pruned
            # starting with most expensive
            # pruned are set as off-grid, next algorithm will determine which
            # to keep
            new_grid_pop = sum(n['pop'] for n in self.nodes if n['conn_start'] == 0 and n['conn_end'] == 1)
            target_new_grid_pop = 1.1 * new_grid_pop * s/steps

            while True:
                current_new_grid_pop = sum(n['pop'] for n in self.nodes if n['conn_start'] == 0 and n['conn_end'] == 1)
                if current_new_grid_pop < target_new_grid_pop:
                    #print('Kept', current_new_grid_pop, 'of', new_grid_pop, 'new grid pop')
                    break

                # Find the most expensive node
                index_most_expensive_node = None
                most_expensive = 0
                for node in self.nodes:
                    if node['conn_start'] == 0 and node['conn_end'] == 1:
                        if len(node['arcs']) == 1:
                            cost_per_person = node['grid_cost']/node['pop']
                            if cost_per_person > most_expensive:
                                most_expensive = cost_per_person
                                index_most_expensive_node = node['i']
                
                # If one is found
                if index_most_expensive_node:
                    # Remove the most expensive node
                    self.nodes[index_most_expensive_node]['conn_end'] = 0

                    # Disable the arc that came to it
                    arc_index = self.nodes[index_most_expensive_node]['arcs'][0]
                    self.network[arc_index]['enabled'] = 0

                    # And remove that arc from the node that preceded it
                    if self.network[arc_index]['ne'] == index_most_expensive_node:
                        prev_node = self.network[arc_index]['ns']
                    else:
                        prev_node = self.network[arc_index]['ne']
                    self.nodes[prev_node]['arcs'].remove(arc_index)

            # Convert results to GeoDataFrames
            self.spatialise()

            quant = s/steps
            # fully densify the most highly densified clusters
            to_densify = self.targets_out.loc[self.targets_out['coverage'] < 1, 'coverage'].quantile(1 - quant)
            self.targets_out.loc[self.targets_out['coverage'] >= to_densify, 'coverage'] = 1

            # og connect only the cheapest x% of og
            to_og = self.targets_out.loc[self.targets_out['type'] == 'off-grid', 'og_cost'].quantile(quant)
            self.targets_out.loc[(self.targets_out['type'] == 'off-grid') & (self.targets_out['og_cost'] > to_og), 'type'] = 'none'

            # Disable arcs that aren't connecting anything
            for i, row in self.targets_out.iterrows():
                if row['type'] == 'none':
                    connected_arcs = self.nodes[i]['arcs']
                    for arc in connected_arcs:
                        if arc in self.network_out.index:
                            self.network_out.drop(arc, axis='index')

            # Calculate population and GDP at the end of this step
            self.targets_out['pop'] = self.targets_out['pop'] * (1 + self.pop_growth * years_per_step) 
            self.targets_out['gdp'] = self.targets_out['gdp'] * (1 + self.gdp_growth * years_per_step)
            self.summary()

            # Yield results
            yield self.targets_out, self.network_out, self.results

            # And prepare targets for the next run
            self.targets_out.loc[self.targets_out['type'] == 'grid', 'conn_start'] = 1
            self.targets = self.targets_out.copy()
            self.targets['conn_end'] = self.targets['conn_start']


    def baseline(self):
        """
        Filter on population and assign whether currently electrified.
        """
        
        self.targets = self.targets.assign(conn_start=0, og_cost=0, grid_cost=0)
        self.targets.loc[self.targets['grid'] <= self.grid_dist_connected, 'conn_start'] = 1
        self.targets.loc[self.targets['ntl'] <= self.min_ntl_connected, 'conn_start'] = 0
        self.targets = self.targets.loc[self.targets['pop'] > self.minimum_pop]

        self.targets['conn_end'] = self.targets['conn_start']


    def connect_targets(self):
        """
        Create an MST connecting the target features.
        """

        columns = ['x', 'y', 'area', 'pop', 'demand', 'conn_start', 'conn_end', 'og_cost', 'grid_cost']
        self.network, self.nodes = network.create_network(self.targets, existing_network=True, 
            columns=columns)


    def spatialise(self, filter_network=True):
        """
        Basic filtering and processing on results.
        Targets 'type' can be one of:
        - densify: was always connected
        - grid: new grid connection
        - off-grid: new off-grid connection
        TODO Add no-connection type.

        Parameters
        ----------
        network, targets : GeoDataFrame
            Output from model.
        """

        self.network_out = io.spatialise(self.network, type='line')

        # Only keep new network lines created by model
        # TODO this should happen automatically somewhere else
        if filter_network:
            self.network_out = self.network_out.loc[self.network_out['existing'] == 0].loc[self.network_out['enabled'] == 1]

        self.targets_out = io.merge_geometry(self.nodes, self.targets,
                                             columns=['i', 'conn_end', 'og_cost', 'grid_cost'])

        # Assign target type based on model results
        self.targets_out['type'] = ''
        self.targets_out.loc[(self.targets_out['conn_end'] == 1) & (self.targets_out['conn_start'] == 1), 'type'] = 'densify'
        self.targets_out.loc[(self.targets_out['conn_end'] == 1) & (self.targets_out['conn_start'] == 0), 'type'] = 'grid'
        self.targets_out.loc[self.targets_out['conn_end'] == 0, 'type'] = 'off-grid'


    def initial_access(self):
        """
        Calibrate initial electricity access levels (per electrified cluster)
        to match national statistics.
        """

        self.targets['coverage'] = util.assign_coverage(self.targets, access_rate=self.access_tot)


    def demand_levels(self, factor=None):
        """
        # TODO Add productive use, schools
        """

        self.targets = self.targets.assign(demand=0)

        if not factor:
            mtf = {
                1: 0.36,
                2: 6,
                3: 30,
                4: 102,
                5: 246
            }

            q25 = self.targets['gdp'].quantile(0.25)
            q50 = self.targets['gdp'].quantile(0.25)
            q75 = self.targets['gdp'].quantile(0.75)
            
            self.targets.loc[self.targets['gdp'] >= q75, 'demand'] = mtf[4]
            self.targets.loc[self.targets['gdp'] < q75, 'demand'] = mtf[3]
            self.targets.loc[self.targets['gdp'] < q50, 'demand'] = mtf[2]
            self.targets.loc[self.targets['gdp'] < q25, 'demand'] = mtf[1]

        else:  # calculate directly
            self.targets['demand'] = factor * np.log(self.targets['gdp'])
            self.targets.loc[self.targets['demand'] < 0, 'demand'] = 0
            

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
        # TODO incorporate SHS and other options
        for node in self.nodes:
            if node['conn_start'] == 0:
                _, local_lv, _ = util.calc_lv(node['pop'], node['demand'], self.people_per_hh, node['area'])

                node['og_cost'] = node['pop']*self.demand_per_person_kw_peak*self.mg_gen_cost + \
                                    local_lv * self.grid_lv_cost + \
                                    node['pop']*self.mg_conn_cost / self.people_per_hh

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
                            self.network, self.nodes, b_demand, b_length, b_nodes, b_arcs = find_best(
                                self.network, self.nodes, arc[goto], arc['i'], 0, 1e-9, [], [], 0, 1e-9, [], [])                

                            # calculate the mg and grid costs of the resultant configuration
                            best_nodes = [self.nodes[i] for i in b_nodes]
                            best_arcs = [self.network[i] for i in b_arcs]
                            mg_cost = sum([node['og_cost'] for node in best_nodes])

                            for node in best_nodes:
                                local_mv, local_lv, transformers = util.calc_lv(node['pop'], node['demand'], self.people_per_hh, node['area'])
                                lv_cost = local_mv * self.grid_mv_cost + local_lv * self.grid_lv_cost + transformers * self.grid_trans_cost
                                conn_cost = self.grid_conn_cost * node['pop'] / self.people_per_hh
                                self.nodes[node['i']]['grid_cost'] = lv_cost + conn_cost

                            # The network direction comes before the optimisation
                            # So it can be either ns or ne that is valid.
                            best_nodes_indices = [node['i'] for node in best_nodes]
                            for arc in best_arcs:
                                if arc['ne'] in best_nodes_indices:
                                    self.nodes[arc['ne']]['grid_cost'] += self.grid_mv_cost * arc['len']
                                elif arc['ns'] in best_nodes_indices:
                                    self.nodes[arc['ns']]['grid_cost'] += self.grid_mv_cost * arc['len']
                                else:
                                    raise Exception('This arc isnt connected to best_nodes')
                            grid_cost = sum(node['grid_cost'] for node in best_nodes)

                            if grid_cost < mg_cost:
                                # check if any nodes are already in to_be_connected
                                add = True
                                for index, item in enumerate(to_be_connected):
                                    if set(b_nodes).intersection(item[1]):
                                        if b_demand/b_length < item[0]:
                                            del to_be_connected[index]
                                        else:
                                            add = False  # if the existing one is better, we don't add the new one
                                        break

                                if add:
                                    to_be_connected.append((b_demand/b_length, b_nodes, b_arcs))
                
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

        Returns
        -------
        results : dict
            Dict of summary results.
        """

        grid = self.targets_out.loc[self.targets_out['type'] == 'grid']
        off_grid = self.targets_out.loc[self.targets_out['type'] == 'off-grid']
        densify = self.targets_out.loc[self.targets_out['type'] == 'densify']
        none = self.targets_out.loc[self.targets_out['type'] == 'none']

        cost_off_grid = off_grid['og_cost'].sum()
        cost_grid = self.grid_mv_cost * self.network_out['len'].sum() + \
                    self.grid_lv_cost * grid['area'].sum() + \
                    self.grid_conn_cost * grid['pop'].sum() / self.people_per_hh
        cost_densify = self.grid_lv_cost * (densify['area'] * (1 - densify['coverage'])).sum() + \
                       self.grid_conn_cost * (densify['pop'] * (1 - densify['coverage'])).sum()
        cost_tot = cost_off_grid + cost_grid + cost_densify

        model_pop = self.targets_out['pop'].sum()
        already_elec_pop = (densify['pop'] * densify['coverage']).sum()
        densify_pop = (densify['pop'] * (1 - densify['coverage'])).sum()

        # tags must match those in the config file
        self.results = {
            'none': len(none),
            'new-grid': len(grid),
            'new-off-grid': len(off_grid),
            'densify': len(densify),
            'cost-grid': cost_grid,
            'cost-off-grid': cost_off_grid,
            'cost-densify': cost_densify,
            'tot-cost': cost_tot,
            'model-pop': model_pop,
            'already-elec-pop': already_elec_pop,
            'densify-pop': densify_pop,
            'new-conn-pop': grid['pop'].sum(),
            'new-og-pop': off_grid['pop'].sum()
        }

        return self.results


def find_best(network, nodes, index, prev_arc, b_demand, b_length, b_nodes, b_arcs, c_demand, c_length, c_nodes, c_arcs):
    """
    This function recurses through the network, dragging a current c_ values along with it.
    These aren't returned, so are left untouched by aborted side-branch explorations.
    The best b_ values are returned, and are updated whenever a better configuration is found.
    Thus these will remember the best solution including all side meanders.
    """

    if nodes[index]['conn_end'] == 0:  # don't do anything with already connected nodes
        c_demand += nodes[index]['demand']
        c_length += network[prev_arc]['len']
        c_nodes = c_nodes[:] + [index]
        c_arcs = c_arcs[:] + [prev_arc]
            
        if c_demand/c_length > b_demand/b_length:
            b_demand = c_demand
            b_length = c_length
            b_nodes[:] = c_nodes[:]
            b_arcs[:] = c_arcs[:]
    
        connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
        for arc in connected_arcs:
            if arc['enabled'] == 0 and arc['i'] != prev_arc:

                goto = 'ne' if arc['ns'] == index else 'ns'  # make sure we look at the other end of the arc
                network, nodes, b_demand, b_length, b_nodes, b_arcs = find_best(
                    network, nodes, arc[goto], arc['i'], b_demand, b_length, b_nodes, b_arcs, c_demand, c_length, c_nodes, c_arcs)
                
    return network, nodes, b_demand, b_length, b_nodes, b_arcs
