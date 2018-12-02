"""
prioritising module for openelec

(c) Chris Arderne
"""

from math import sqrt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path

def priority(clusters, min_grid_dist=1000, max_ntl=50):
    """
    Calculate the priority clusters that meet the criteria,
    and calculate a score from 1-5 for each.

    Parameters
    ----------
    clusters: GeoDataFrame
        Village clusters object.
    min_grid_dist: int
        Minimum distance from grid in metres to consider for clusters.
    max_ntl: int
        Maximum value of NTL (night time lights) to consider.
        Range 0-255.

    Returns
    -------
    clusters: GeoDatFrame
        Processed clusters.
    summary: dict
        Summary results.
    """

    clusters = clusters.loc[clusters['grid_dist'] > min_grid_dist]
    clusters = clusters.loc[clusters['ntl'] < max_ntl]

    def get_score(row):
        grid_score = 0
        if row['grid_dist'] > 5000:
            grid_score = 1
        elif row['grid_dist'] > 10000:
            grid_score = 2

        pop_score = 0
        if row['pop'] > 500:
            pop_score = 1
        elif row['pop'] > 1000:
            pop_score = 2
        elif row['pop'] > 2000:
            pop_score = 3

        return grid_score + pop_score

    clusters['score'] = clusters.apply(get_score, axis=1)
    clusters = clusters.to_crs(epsg=4326)

    summary = {
        'num-clusters': len(clusters)
    }

    return clusters, summary
