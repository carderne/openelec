# network.py
#!python3

"""
network module of openelec.
Provides functionality for creating MST and network from input points.
"""

from math import sqrt

import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.neighbors import kneighbors_graph
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy import sparse
from shapely.geometry import Point

EPSG4326 = {'init': 'epsg:4326'}
# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


def create_network(targets, columns, existing_network=False, directed=False, origin=None):
    """
    We then take all the clusters and calculate the optimum network that connects them all together.
    We use this to create a graph network of and nodes and arcs representing the clusters and connections.

    Parameters
    ----------
    clusters : GeoDataFrame
        The prepared clusters.
    columns : list
        List of columns to include.
    existing_network : boolean, optional (default False.)
        Whether there is an existing network.
        In this case, redundant lines in new network are removed.
    directed : boolean, optional (default False.)
        Whether the output network should be directed.
    origin : tuple, optional
        Location of an origin (e.g. generator) for the network.
        Should be of the form (latitude, longitude) in WGS84 coordinates.
        If not provided, the first element is set as origin.
    
    Returns
    -------
    network : list of dicts
        The network arcs.
    nodes : list of dicts
        The network nodes.
    """

    points = targets.to_crs(EPSG102022)
    points.geometry = points['geometry'].centroid
    points['x'] = points.geometry.x
    points['y'] = points.geometry.y
    points = points[columns]

    if origin:
        points = add_origin(points, origin)

    # This point and line data is then copied into two arrays, called network and nodes,
    # containing the lines and clusters, respectively. Each element represents a single cluster or joining arc,
    # and has data within describing the coordinates and more.
    nodes = []
    for index, row in points.iterrows():
        row_dict = row.to_dict()
        row_dict['i'] = index
        row_dict['arcs'] = []
        nodes.append(row_dict)

    mst_points = points[['x', 'y']].values
    start_points, end_points, nodes_connected = spanning_tree(mst_points, approximate=True)

    network = []
    for i, (s, e, n) in enumerate(zip(start_points, end_points, nodes_connected)):
        xs = int(s[0])
        ys = int(s[1])
        xe = int(e[0])
        ye = int(e[1])
        length = int(sqrt((xe - xs)**2 + (ye - ys)**2))

        ns = n[0]
        ne = n[1]

        nodes[ns]['arcs'].append(i)
        nodes[ne]['arcs'].append(i)

        network.append({'i': i, 'xs': xs, 'ys': ys, 'xe': xe, 'ye': ye, 'ns': ns, 'ne': ne, 'len': length, 'enabled': 1, 'existing': 1,})
    
    if existing_network:
        network = remove_existing(network, nodes)
        
    if directed:
        network = direct_network(network, nodes, 0, None)

    return network, nodes


def spanning_tree(X, approximate=False):
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

    if approximate:
        n_neighbors = 50

    else:
        n_neighbors = len(X) - 1

    n_neighbors = min(n_neighbors, len(X) - 1)
    if n_neighbors < 2:
        raise ValueError('Need at least three sample points')

    G = kneighbors_graph(X, n_neighbors=n_neighbors, mode='distance')
    full_tree = minimum_spanning_tree(G, overwrite=True)

    X = np.asarray(X)
    if X.ndim != 2 or X.shape[1] != 2:
        raise ValueError('shape of X should be (n_samples, 2)')

    coo = sparse.coo_matrix(full_tree)
    A = X[coo.row].T
    B = X[coo.col].T

    start_points = [(Ax, Ay) for Ax, Ay in zip(A[0], A[1])]
    end_points = [(Bx, By) for Bx, By in zip(B[0], B[1])]
    nodes_connected = [(s, e) for s, e in zip(coo.row, coo.col)]

    return start_points, end_points, nodes_connected


def add_origin(points, origin):
    """
    If origin not specified, the model defaults to using index 0 as the 'main' point
    Thus targets should already have been sorted by population/area with largest first
    """

    gen_lat = float(origin[0])
    gen_lng = float(origin[1])
    pv_point = gpd.GeoDataFrame(crs=EPSG4326, geometry=[Point([gen_lng, gen_lat])])
    pv_point_projected = pv_point.to_crs(EPSG102022)
    pv_point_df = [{'x': float(pv_point_projected.geometry.x), 'y': float(pv_point_projected.geometry.y), 'area': 0}]
    points = pd.concat([pd.DataFrame(pv_point_df), points], ignore_index=True, sort=False)
    points = points.fillna(value=0)

    return points


def remove_existing(network, nodes):
    """
    Set which arcs don't already exist (and the remainder do!)
    """

    for node in nodes:
        if node['conn_start'] == 0:
            connected_arcs = [network[arc_index] for arc_index in node['arcs']]
            for arc in connected_arcs:
                network[arc['i']]['existing'] = 0
                network[arc['i']]['enabled'] = 0
    
    return network


def direct_network(network, nodes, index, prev):
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
    -------`
    network: list of lists
        Nearby network directed for current node.
    nodes: list of list
        The nodes object.
    """

    connected_arcs = nodes[index]['arcs']
    for arc_index in connected_arcs:
        if arc_index == prev:
            continue

        arc = network[arc_index]
        if not arc['ns'] == index:
            arc['ne'] = arc['ns']
            arc['ns'] = index

            xs_new = arc['xe']
            ys_new = arc['ye']
            arc['xe'] = arc['xs']
            arc['ye'] = arc['ys']
            arc['xs'] = xs_new
            arc['ys'] = ys_new

        network = direct_network(network, nodes, arc['ne'], arc_index) # and investigate downstream from this node

    for arc in network:
        nodes[arc['ne']]['marg_dist'] = arc['len']

    return network
