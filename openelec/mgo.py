"""
minigrid-optimiser
Tool designed to take a small village and estimate the optimum connections, based on a PV installation location and economic data.
"""

import json
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from math import sqrt
import geopandas as gpd
import os.path
from collections import defaultdict
from sklearn.neighbors import kneighbors_graph
from scipy.sparse.csgraph import minimum_spanning_tree, connected_components
from scipy import sparse

# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


def village_centroids(file_dir):
    """
    Get list of available villages together with their centroids.

    Parameters
    ----------
    file_dir: string
        The path containing the GeoJSON files to be considered.

    Returns
    -------
    villages: dict
        dict key on village names, each item containng a dict
        with the centroid {'lat': latitude, 'lng': longitude}.
    """
    villages = defaultdict(tuple)

    for file in os.listdir(file_dir):
        if file.endswith('.geojson'):

            name = os.path.splitext(file)[0]

            gdf = gpd.read_file(os.path.join(file_dir, file))
            lng = gdf.geometry.centroid.x.mean()
            lat = gdf.geometry.centroid.y.mean()

            villages[name] = {'lat': lat, 'lng': lng}

    return villages


def load_buildings(village, file_dir=None, min_area=20):
    """
    Load the relevant GeoJSON, add an area column and
    filter to exclude buildings too small.

    Parameters
    ----------
    village_name: string
        The village's name.
    file_dir: string
        The directory containing the GeoJSON file.
    min_area: int
        Exclude buildings below this size in m2.

    Returns
    -------
    buildings: geopandas.GeoDataFrame
        All of the buildings with attribues and geometries.
    """

    min_area = float(min_area)

    try:
        village = json.loads(village)
        buildings = gpd.GeoDataFrame.from_features(village, crs={'init': 'epsg:4326'})

    except json.JSONDecodeError:
        input_file = '{}/{}.geojson'.format(file_dir, village)
        buildings = gpd.read_file(input_file)
    
    # project to equal-area before calculating area
    buildings_projected = buildings.to_crs(EPSG102022)

    buildings_projected["area"] = buildings_projected['geometry'].area
    buildings_projected = buildings_projected.loc[buildings_projected['area'] > min_area]

    # Sort with largest building first so that if no gen point specified,
    # the largest building will be treated as the 'center' of the network
    buildings_projected = buildings_projected.sort_values('area', ascending=False)

    # project back to WGS84
    buildings = buildings_projected.to_crs(epsg=4326)
    buildings = buildings.reset_index().drop(columns=['index'])

    return buildings


def create_network(buildings, specify_gen=False, gen_lat=None, gen_lng=None):
    """
    Create a network of lines and nodes from the buildings file,
    using a Minimum spanning tree to generate the connecting
    lines between the buildings.

    Parameters
    ----------
    buildings: geopandas.GeoDataFrame
        All of the buildings with attribues and geometries.
    specify_gen: boolean, optional, default False
    gen_lat: float, optional
        Latitude of PV generator.
    gen_lng: float, optional
        Longitude of PV generator.

    Returns
    -------
    network: list of dicts
        Each dict within contains a single network arc, with the following attributes:
        index, xs, ys, xe, ye, ns, ne, dir, len, enabled
    nodes: list of dicts
        Each dict within contains a single building node, with the main point at index 0.
        Each element has the following attributes:
        index, x, y, area, marg_dist, tot_dist, conn, arcs
    """

    buildings_projected = buildings.to_crs(EPSG102022)

    buildings_points = buildings_projected.copy()
    buildings_points.geometry = buildings_points['geometry'].centroid
    buildings_points['X'] = buildings_points.geometry.x
    buildings_points['Y'] = buildings_points.geometry.y

    # We then take all the houses and calculate the optimum network that connects them all to the PV point,
    # before we start analysing further and deciding on the optimum network.
    df = pd.DataFrame(buildings_points)

    # If generator location not specified, the model defaults to using building index 0 as the 'main' point
    # This is the largest, due to sort by area in load_buildings()
    # TODO Add option to use center of gravity instead?
    if specify_gen:
      gen_lat = float(gen_lat)
      gen_lng = float(gen_lng)
      pv_point = gpd.GeoDataFrame(crs={'init': 'epsg:4326'}, geometry=[Point([gen_lng, gen_lat])])
      pv_point_projected = pv_point.to_crs(EPSG102022)
      pv_point_df = [{'X': pv_point_projected.geometry.x, 'Y': pv_point_projected.geometry.y, 'area': 0}]
      df = pd.concat([pd.DataFrame(pv_point_df), df], ignore_index=True)

    points = df[['X', 'Y']].as_matrix()

    T_x, T_y = get_spanning_tree(points)

    # This point and line data is then copied into two arrays, called *nodes* and *network*,
    # containing the houses and lines, respectively.
    # Each element represents a single house or joining arc, and has data within describing the coordinates and more.
    # astype(int) doesn't round - it just chops off the decimals
    nodes_list = df[['X', 'Y', 'area']].reset_index().values.astype(int).tolist()
    nodes = []
    for n in nodes_list:
        nodes.append({'i': n[0], 'x': n[1], 'y': n[2], 'area': n[3], 'marg_dist': 0, 'tot_dist': 0, 'conn': 0, 'arcs': []})
        
    counter = 0
    network = []
    for xs, ys, xe, ye in zip(T_x[0], T_y[0], T_x[1], T_y[1]):
        network.append({'i': counter, 'xs': int(xs), 'ys': int(ys), 'xe': int(xe), 'ye': int(ye), 'ns':-99, 'ne':-99, 'dir':0, 'len':0, 'enabled':1})
        counter += 1
        
    # add the length for each arc
    for arc in network:
        arc['len'] = sqrt((arc['xe'] - arc['xs'])**2 + (arc['ye'] - arc['ys'])**2)

    network, nodes = direct_network(network, nodes, 0)

    # for every node, add references to every arc that connects to it
    for arc in network:
        nodes[arc['ns']]['arcs'].append(arc['i'])
        nodes[arc['ne']]['arcs'].append(arc['i'])

    return network, nodes


def get_spanning_tree(X):
    """
    Function to calculate the Minimum spanning tree connecting the provided points X.
    Modified from astroML code in mst_clustering.py

    Parameters
    ----------
    X: array_like
        2D array of shape (n_sample, 2) containing the x- and y-coordinates of the points.

    Returns
    -------
    x_coords, y_coords : ndarrays
        the x and y coordinates for plotting the graph.  They are of size
        [2, n_links], and can be visualized using
        ``plt.plot(x_coords, y_coords, '-k')``
    """

    n_neighbors = len(X) - 1
    if n_neighbors < 2:
        raise ValueError('Need at least three sample points')

    G = kneighbors_graph(X, n_neighbors=n_neighbors, mode='distance')
    full_tree = minimum_spanning_tree(G, overwrite=True)

    X = np.asarray(X)
    if (X.ndim != 2) or (X.shape[1] != 2):
        raise ValueError('shape of X should be (n_samples, 2)')

    coo = sparse.coo_matrix(full_tree)
    A = X[coo.row].T
    B = X[coo.col].T

    x_coords = np.vstack([A[0], B[0]])
    y_coords = np.vstack([A[1], B[1]])

    return x_coords, y_coords


def direct_network(network, nodes, index):
    """
    Recursive function to direct the network from the PV point outwards
    We need to calculate the directionality of the network, starting from the PV location and
    reaching outwards to the furthest branches.
    We use this to calculate, for each node, it's marginal and total distance from the PV location.
    At the same time, we tell each arc which node is 'upstream' of it, and which is 'downstream'.
    We also tell each node which arcs (at least one, up to three or four?) it is connected to.

    Parameters
    ----------
    network: list of dicts
        Containing the arc representations.
    nodes: list of dicts
        Containing the building node representations.
    index: int
        Current node index that we're looking at.

    Returns
    -------
    network: list of lists
        Nearby network directed for current node.
    nodes: list of list
        The nodes object.
    """
    for arc in network:
        found = False
        if arc['xs'] == nodes[index]['x'] and arc['ys'] == nodes[index]['y']:
            # make sure we haven't done this arc already!
            if arc['dir'] == 1:
                continue
            found = True
            
        elif arc['xe'] == nodes[index]['x'] and arc['ye'] == nodes[index]['y']:
            # make sure we haven't done this arc already!
            if arc['dir'] == 1:
                continue
            found = True
            
            # flip it around because it's pointing the wrong way
            xs_new = arc['xe']
            ys_new = arc['ye']
            arc['xe'] = arc['xs']
            arc['ye'] = arc['ys']
            arc['xs'] = xs_new
            arc['ys'] = ys_new
            
        if found:    
            arc['ns'] = nodes[index]['i'] # tell this arc that this node is its starting point
            arc['dir'] = 1 # so we know this arc has been done
            
            for node in nodes:
                if node['x'] == arc['xe'] and node['y'] == arc['ye']:
                    arc['ne'] = node['i'] # tell this arc that this node is its ending point
                    node['marg_dist'] = arc['len'] # assign arc length to node's marginal distance
                    node['tot_dist'] = nodes[index]['marg_dist'] + arc['len'] # and calculate total distance
                    
                    # If this building exceeds the maximum total length allowed, disable the arc connecting it
                    # The later algorithms respect this settings
                    # DISABLED
                    # if node[5] > max_length:
                    #    arc[9] = 0
                    
                    network, nodes = direct_network(network, nodes, node['i']) # and investigate downstream from this node
                    break

    return network, nodes


def run_model(network, nodes, demand, tariff, gen_cost, cost_wire, cost_connection,
              opex_ratio, years, discount_rate, target_coverage=-1):
    """
    Run the model with the given economic parameters and return the processed network and nodes.

    Parameters
    ----------
    network: list of dicts
        Containing the arc representations.
    nodes: list of dicts
        Containing the building node representations.
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
    target_coverage: float, optional
        If provided, model will aim to achieve this level of population coverage,
        rather than optimising on NPV.
    """
    
    demand_per_person_kwh_month = float(demand)
    tariff = float(tariff)
    gen_cost_per_kw = float(gen_cost)
    cost_wire = float(cost_wire)
    cost_connection = float(cost_connection)
    opex_ratio = float(opex_ratio)
    years = int(years)
    discount_rate = float(discount_rate)

    # be flexible to inputs as percentage or decimals
    if opex_ratio >= 1:
        opex_ratio /= 100
    if discount_rate >= 1:
        discount_rate /= 100

    # Here we prepare the algorithm to optimise our network configuration, by pruning network extensions that aren't profitable.
    # Here the economic data should be entered.
    # optimisation strategy #2
    # cut arcs one by one, see which cut is the *most* profitable, and then take that network and repeat the process
    # annual income should be specified by the nodes

    num_people_per_m2 = 0.15  # bit of a guess that there are 4 people in 40m2 house
    demand_per_person_kw_peak = demand_per_person_kwh_month / (4*30)  # 130 is based on MTF numbers, should use a real demand curve
    gen_size_kw = sum([n['area'] for n in nodes]) * num_people_per_m2 * demand_per_person_kw_peak
    cost_gen = gen_size_kw * gen_cost_per_kw


    def calculate_profit(nodes, network, index, disabled_arc_index, cost, income_per_month):
        # here we recurse through the network and calculate profit
        # start with all arcs that connect to the index node, and get the end-nodes for those arcs
        # calculate profit on those nodes, and then recurse!
        # disabled_arc should be treated as if disabled
        
        # first calculate the profitability of thise node?
        cost += cost_wire * nodes[index]['marg_dist'] + cost_connection
        income_per_month += nodes[index]['area'] * num_people_per_m2 * demand_per_person_kwh_month * tariff
        
        connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
        for arc in connected_arcs:
            if arc['enabled'] == 1 and arc['i'] != disabled_arc_index and arc['ns'] == index:
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, arc['ne'], disabled_arc_index, cost, income_per_month)
                
        return cost, income_per_month, nodes, network


    # Then we start with the complete network, and try 'deleting' each arc.
    # Whichever deletion is the most profitable, we make it permanent and
    # repeat the process with the new configuration.
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
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, 0, arc['i'], 0, 0)

                capex = cost_gen + cost
                opex = (opex_ratio * capex)
                income = income_per_month * 12
                
                flows = np.ones(years) * (income - opex)
                flows[0] = -capex
                npv = np.npv(discount_rate, flows)
                
                counter += 1
                
                # check if this is the most profitable yet
                if npv > best_npv:
                    found = True
                    best_npv = npv
                    best_npv_index = arc['i']
            if found:
                # disable that arc
                network[best_npv_index]['enabled'] = 0

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
                cost, income_per_month, nodes, network = calculate_profit(nodes, network, 0, arc['i'], 0, 0)
        
                capex = cost_gen + cost
                opex = (opex_ratio * capex)
                income = income_per_month * 12
                
                flows = np.ones(years) * (income - opex)
                flows[0] = -capex
                npv = np.npv(discount_rate, flows)
                
                counter += 1
        
                # check if this is the most profitable yet
                if npv > best_npv and arc['enabled'] == 1:
                    found = True
                    best_npv = npv
                    best_npv_index = arc['i']
                    
            if found:
                # disable that arc
                network[best_npv_index]['enabled'] = 0
        
            actual_coverage = len([arc for arc in network if arc['enabled'] == 1])/total_arcs
            if actual_coverage <= target_coverage:
                break
                                
    # Then we disconnect all the houses that are no longer served by active arcs,
    # and prune any stranded arcs that remained on un-connected paths.
    # now we need to tell the houses that aren't connected, that they aren't connected (or vice-versa)
    # recurse from the starting point and ID connected houses as connected?
    def connect_houses(nodes, network, index):
        # start from base, follow connection (similar to calculate_profit) and swith node[6] to 1 wherever connected
        # and only follow the paths of connected houses
        
        # this node is connected
        nodes[index]['conn'] = 1
        
        connected_arcs = [network[arc_index] for arc_index in nodes[index]['arcs']]
        for arc in connected_arcs:
            if arc['enabled'] == 1 and arc['ns'] == index:
                connect_houses(nodes, network, arc['ne'])
                
        return nodes, network
        
    nodes, network = connect_houses(nodes, network, 0)

    # and do the same for the stranded arcs
    for node in nodes:
        if node['conn'] == 0:
            connected_arcs = [network[arc_index] for arc_index in node['arcs']]
            for arc in connected_arcs:
                arc['enabled'] = 0


    # And calculate some quick summary numbers for the village
    # create a quick report
    # number connected, length of line, total profit over ten years
    count_nodes = 0
    income_per_month = 0
    gen_size_kw = 0
    for node in nodes:
        if node['conn'] == 1:
            count_nodes += 1
            income_per_month += node['area'] * num_people_per_m2 * demand_per_person_kwh_month * tariff
            gen_size_kw += node['area'] * num_people_per_m2 * demand_per_person_kw_peak
    
    count_nodes -= 1  # so we don't count the generator

    total_length = 0.0
    for arc in network:
        if arc['enabled'] == 1:
            total_length += arc['len']

    capex = gen_size_kw * gen_cost_per_kw + cost_connection * count_nodes + cost_wire * total_length
    opex = (opex_ratio * capex)
    income = income_per_month * 12

    flows = np.ones(years) * (income - opex)
    flows[0] = -capex
    npv = np.npv(discount_rate, flows)

    results = {'connected': count_nodes,
               'gen-size': int(gen_size_kw),
               'line-length': int(total_length),
               'capex': int(capex),
               'opex': int(opex),
               'income': int(income),
               'npv': int(npv)}

    return results, network, nodes


def network_to_spatial(buildings, network, nodes):
    """
    Create GeoDataFrames with geometries from the network.

    Parameters
    ----------
    buildings: geopandas.GeoDataFrame
        Original buildings with WGS84 geometries. Used to join nodes into.
    network: list of dicts
        Containing the arc representations.
    nodes: list of dicts
        Containing the building node representations.

    Returns
    -------
    network_gdf: geopandas.GeoDataFrame
        Resultant optimised network.
    buildings_gdf: geopandas.GeoDataFrame
        Resultant buildings filtered to only include those connected.
    """
    # And then do a spatial join to get the results back into a polygon shapefile
    # join the resultant points with the orignal buildings_projected
    # create geometries from X and Y points and create gdf

    nodes_df = pd.DataFrame(nodes)
    if nodes_df.loc[0, 'area'] == 0:
        nodes_df.index = nodes_df.index - 1  # to get rid of pv point
    nodes_df = nodes_df.drop(columns=['area', 'arcs'])
    buildings_gdf = buildings.merge(nodes_df, left_index=True, right_index=True)
    buildings_gdf = buildings_gdf.loc[buildings_gdf['conn'] == 1]

    network_df = pd.DataFrame(network)
    network_geometry = [LineString([(arc['xs'], arc['ys']), (arc['xe'], arc['ye'])]) for arc in network]
    network_gdf = gpd.GeoDataFrame(network_df, crs=EPSG102022, geometry=network_geometry)
    network_gdf = network_gdf.to_crs(epsg=4326)
    network_gdf = network_gdf.loc[network_gdf['enabled'] == 1]

    return network_gdf, buildings_gdf


def gdf_to_geojson(gdf, property_cols=[]):
    """
    Convert GeoDataFrame to GeoJSON that can be supplied to JavaScript.

    Parameters
    ----------
    gdf: geopandas.GeoDataFrame
        GeoDataFrame to be converted.
    property_cols: list, optional
        List of column names from gdf to be included in 'properties' of each GeoJSON feature.

    Returns
    -------
    geoJson: dict
        A GeoJSON representatial
        List of column names from gdf to be included in 'properties' of each GeoJSON feature.

    Returns
    -------
    geoJson: dict
        A GeoJSON representation that can be parsed by standard JSON readers.
    """
    geoJson = {'type': 'FeatureCollection',
           'features': []}    

    for _, row in gdf.iterrows():
        geoJson['features'].append({
            'type': 'Feature',
            'geometry': get_geometry(row['geometry']),
            'properties': get_properties(row, property_cols)
        })

    return geoJson


def get_geometry(geometry):
    """
    Convert a GeoDataFrame geometry value into a GeoJSON-friendly representation.

    Parameters
    ----------
    geometry: shapely.LineString, shapely.Polygon or shapely.MultiPolygon
        A single geometry entry from a GeoDataFrame.

    Returns
    -------
    geom_dict: dict
        A GeoJSON geometry element of the form
        'geometry': {
            'type': type,
            'coordinates': coords
        } 
    """
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
    """
    Get the selected columns from the pandas row as a GeoJSON-friendly dict.

    Parameters
    ----------
    row: pandas.Series
        A single row from a GeoDataFrame.
    property_cols: list
        List of column names to be added.

    Returns
    -------
    properties: dict
        A GeoJSON element of the form
        properties: {
            'column1': property1,
            'column2': property2,
            ...
        }
    """
    properties = {}
    
    for col in property_cols:
        properties[col] = row[col]
        
    return properties
