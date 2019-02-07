# io.py
#!python3

"""
Module for loading and saving.

GPL-3.0 (c) Chris Arderne
"""

from pathlib import Path
import json

import requests
import pandas as pd
import geopandas as gpd
import fiona
from shapely.geometry import Point, LineString, Polygon, MultiPolygon

EPSG4326 = {'init': 'epsg:4326'}
# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = '+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


def read_data(data):
    """
    Read targets (clusters, buildings) data from a file or other source.

    Parameters
    ----------
    data : Path, str, dict
        Path to a Fiona-readable file, or GeoJSON-like dict.
        Can also be a string representation of a GeoJSON.

    Returns
    -------
    targets : GeoDataFrame
        The data filtered and processed.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = Path(data)

    if isinstance(data, dict):
        targets = gpd.GeoDataFrame.from_features(data, crs=EPSG4326)

    if isinstance(data, Path):
        targets = gpd.read_file(data)

    targets = targets.dropna(subset=['geometry'])

    # project to equal-area before calculating area
    targets = targets.to_crs(EPSG102022)

    if not 'area' in targets.columns:
        targets['area'] = targets['geometry'].area

    # project back to WGS84
    targets = targets.to_crs(EPSG4326)

    return targets


def merge_geometry(results, geometry, columns=None):
    """
    Merge results from modelling with an original input geometry,
    using the index as key for both.

    Parameters
    ----------
    results : list of dicts
        Output from modelling.
    geometry : GeoDataFrame
        Target geometry with amtching index.
    columns : list, optional
        List of columns to include in output.
        If not provided, keep all.

    Returns
    -------
    spatial : GeoDataFrame
        Results with geometry.
    """

    results_df = pd.DataFrame(results)

    if columns:
        results_df = results_df[columns]

        geom_columns = geometry.columns
        drop_columns = []
        for col in columns:
            if col in geom_columns:
                drop_columns.append(col)
        geometry = geometry.drop(columns=drop_columns)

    if len(results_df) > len(geometry):
        results_df.index = results_df.index - 1  # to get rid of pv point

    spatial = geometry.merge(results_df, how='left', left_index=True, right_index=True)
    spatial = spatial.to_crs(EPSG4326)

    return spatial


def spatialise(results, type='line'):
    """
    Convert results to a GeoDataFrame using values to 
    create a geometry.

    Parameters
    ----------
    results : list of dicts
        An output from the modelling.
    type : str, optional (default 'line'.)
        What type of geometry it is.
        (Currently only implemented for 'line').

    Returns
    -------
    spatial : GeoDataFrame
        Results with geometry.
    """

    results_df = pd.DataFrame(results)
    
    if type == 'line':
        geometry = [LineString([(arc['xs'], arc['ys']), (arc['xe'], arc['ye'])]) for arc in results]
    else:
        raise NotImplementedError('Only implemented for type==line.')

    spatial = gpd.GeoDataFrame(results_df, crs=EPSG102022, geometry=geometry)
    spatial = spatial.to_crs(EPSG4326)

    return spatial


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
    geojson: dict
        A GeoJSON representation that can be parsed by standard JSON readers.
    """

    geojson = {'type': 'FeatureCollection',
           'features': []}

    for _, row in gdf.iterrows():
        geojson['features'].append({
            'type': 'Feature',
            'geometry': geometry(row['geometry']),
            'properties': properties(row, property_cols)
        })

    return geojson


def geometry(coordinates):
    """
    Convert a GeoDataFrame geometry value into a GeoJSON-friendly representation.

    Parameters
    ----------
    coords: shapely.LineString, shapely.Polygon or shapely.MultiPolygon
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
    
    if isinstance(coordinates, LineString):
        geom_dict['type'] = 'LineString'
        geom_dict['coordinates'] = list(coordinates.coords)

    elif isinstance(coordinates, Polygon):
        geom_dict['type'] = 'Polygon'
        geom_dict['coordinates'] = [list(coordinates.exterior.coords)]
    
    elif isinstance(coordinates, MultiPolygon):
        if len(coordinates.geoms) > 1:
            # TODO should handle true multipolygons somehow
            pass
        
        geom_dict['type'] = 'Polygon'
        geom_dict['coordinates'] = [list(coordinates.geoms[0].exterior.coords)]
        
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
        if pd.notna(row[col]):
            prop_dict[col] = row[col]
        else:
            prop_dict[col] = 0
        
    return prop_dict


def overpass(bounds):
    """
    Get OSM Overpass results from specified bounds as GeoJSON.

    Parameters
    ----------
    bounds : str
        String in this format:
        "S, W, N, E"

    Returns
    -------
    geojson : dict
        GeoJSON results.
    """
    
    overpassQuery = 'building'
    nodeQuery = 'node[' + overpassQuery + '](' + bounds + ');'
    wayQuery = 'way[' + overpassQuery + '](' + bounds + ');'
    relationQuery = 'relation[' + overpassQuery + '](' + bounds + ');'
    query = '?data=[out:json][timeout:15];(' + nodeQuery + wayQuery + relationQuery + ');out body geom;'
    baseUrl = 'https://overpass-api.de/api/interpreter'
    resultUrl = baseUrl + query

    response = requests.get(resultUrl)
    items = response.json()['elements']
    geojson = json2geojson(items)

    return geojson


def json2geojson(items):
    """
    Convert a json from OSM Overpass to a GeoJSON.

    Parameters
    ----------
    items : json
        The JSON representation.

    Returns
    -------
    geojson : dict
        As a GeoJSON.
    """

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                 "properties": {},
                 "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [
                            point['lon'],
                            point['lat']
                        ] for point in reversed(feature['geometry'])
                    ]]
                }
            } for feature in items
        ]
    }
    
    return geojson


def save_to_path(path, **features):
    """
    Save the provided features in the directory specified.
    File names are taken from the keywords.
    """

    if isinstance(path, str):
        path = Path(path)

    path.mkdir(parents=True, exist_ok=True)

    for name, feature in features.items():
        name = name + '.geojson'
        feature_path = path / name
        with fiona.Env():
            feature.to_file(feature_path, driver='GeoJSON')
