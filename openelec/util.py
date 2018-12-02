"""
util module for openelec

(c) Chris Arderne
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

def centroid(file_path):
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


def spanning_tree(X):
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

def geojsonify(gdf, property_cols=[]):
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
            'geometry': geometry(row['geometry']),
            'properties': properties(row, property_cols)
        })

    return geoJson


def geometry(geometry):
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


def properties(row, property_cols):
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
    prop_dict: dict
        A GeoJSON element of the form
        properties: {
            'column1': property1,
            'column2': property2,
            ...
        }
    """
    prop_dict = {}
    
    for col in property_cols:
        prop_dict[col] = row[col]
        
    return prop_dict
