# util.py
#!python3

"""
util module for openelec

(c) Chris Arderne
"""

import json
import requests
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from math import sqrt
import geopandas as gpd
import os.path
from collections import defaultdict


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
