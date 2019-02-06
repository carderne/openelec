# prioritise.py
#!python3

"""
prioritising module for openelec

GPL-3.0 (c) Chris Arderne
"""


def priority(clusters, pop_range=None, grid_range=None, ntl_range=None,
             gdp_range=None, travel_range=None):
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

    # extended filtering with ranges
    clusters['consider'] = 1
    if pop_range:
        clusters.loc[~clusters['pop'].between(pop_range[0], pop_range[1]), 'consider'] = 0

    if grid_range:
        clusters.loc[~clusters['grid'].between(grid_range[0], grid_range[1]), 'consider'] = 0
    if ntl_range:
        clusters.loc[~clusters['ntl'].between(ntl_range[0], ntl_range[1]), 'consider'] = 0
    if gdp_range:
        clusters.loc[~clusters['gdp'].between(gdp_range[0], gdp_range[1]), 'consider'] = 0
    if travel_range:
        clusters.loc[~clusters['travel'].between(travel_range[0], travel_range[1]), 'consider'] = 0

    pop_max = clusters.loc[clusters['consider'] == 1, 'pop'].max()
    gdp_max = clusters.loc[clusters['consider'] == 1, 'gdp'].max()
    grid_max = clusters.loc[clusters['consider'] == 1, 'grid'].max()

    def get_score(row):
        gdp_score = row['gdp'] / gdp_max
        pop_score = row['pop'] / pop_max
        grid_score = row['grid'] / grid_max

        return gdp_score + pop_score + grid_score

    clusters['score'] = None
    clusters.loc[clusters['consider'] == 1, 'score'] = clusters.apply(get_score, axis=1)
    max_score = clusters['score'].max()
    clusters['score'] = clusters['score'] / max_score

    clusters = clusters.to_crs(epsg=4326)

    print(len(clusters.loc[clusters['consider'] == 1]))

    summary = {
        'num-clusters': len(clusters.loc[clusters['consider'] == 1])
    }

    return clusters, summary
