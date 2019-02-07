# clustering.py
#!python3

"""
clusters module for openelec

Provides functions to read in a raster population dataset
and convert to discrete vector polgons, each with a set
population value. Additionally calculate each polygon's
distance from a provided grid infrastructure vector.

GPL-3.0 (c) Chris Arderne
"""

import json
from pathlib import Path

import numpy as np
from scipy import ndimage
import geopandas as gpd

import rasterio
from rasterio.mask import mask
from rasterio.features import shapes, rasterize
from rasterstats import zonal_stats


def prepare_clusters(country, ghs_in, gdp_in, travel_in, ntl_in, aoi_in, grid_in, clusters_out):
    """
    Run all.
    """
   
    Path(clusters_out).parents[0].mkdir(parents=True, exist_ok=True)

    print(f'\n\n--- {country} ---\n\n')
    print('Clipping raster...', end='', flush=True)
    boundary = gpd.read_file(aoi_in)
    boundary = boundary.loc[boundary['NAME_0'] == country]
    clipped, affine, crs = clip_raster(raster=ghs_in, boundary=boundary)
    print('\n -- Shape:', clipped[0].shape)
    print('-- Affine:\n', affine)
    
    print('\t\t\tDone\nCreating clusters...', end='', flush=True)
    clusters = create_clusters(raster=clipped, affine=affine, crs=crs)
    
    print('\t\tDone\nFiltering and merging...', end='', flush=True)
    clusters = filter_merge_clusters(clusters=clusters, buffer_amount=200)
    
    print('\tDone\nGetting population...', end='', flush=True)
    # Number of people per cluster
    clusters = add_raster_layer(clusters=clusters, raster=ghs_in, operation='sum', col_name='pop')
    clusters = fix_column(clusters, 'pop', minimum=0)
    
    print('\tDone\nGetting NTL...', end='', flush=True)
    # Value from -0.1ish to about 30? We cut off negative values to minimum 0
    clusters = add_raster_layer(clusters=clusters, raster=ntl_in, operation='max', col_name='ntl', crs={'init': 'epsg:4326'})
    clusters = fix_column(clusters, 'ntl', minimum=0)
    
    print('\tDone\nGetting travel...', end='', flush=True)
    # Travel time to cities, divide by 60m to get hours and replace nan with median
    clusters = add_raster_layer(clusters=clusters, raster=travel_in, operation='median', col_name='travel')
    clusters = fix_column(clusters, 'travel', factor=1/60, no_value='median')
    
    print('\tDone\nGetting GDP...', end='', flush=True)
    # Get GDP in USD/capita for each cluster (input is kUSD per cell)
    clusters = add_raster_layer(clusters=clusters, raster=gdp_in, operation='sum', col_name='gdp')
    clusters = fix_column(clusters, 'gdp', factor=1000, maximum='largest', no_value='median', per_capita=True)
    
    print('\t\tDone\nGetting grid dists...', end='', flush=True)
    # Get grid distance in km
    grid = gpd.read_file(grid_in)
    grid = grid[grid.geometry.intersects(boundary.geometry.unary_union)]
    clusters = add_vector_layer(clusters=clusters, vector=grid, operation='distance', col_name='grid',
                                                shape=clipped[0].shape, affine=affine, raster_crs=crs)
    clusters = fix_column(clusters, 'grid', factor=1/1000)
    
    print('\t\tDone\nSimplifying geometry...', end='', flush=True)
    clusters.geometry = clusters.simplify(tolerance=0.001, preserve_topology=False)
    
    print(f'\t\tDone\nSaving to {str(clusters_out)}...', end='', flush=True)
    clusters['fid'] = clusters.index
    clusters = clusters.dropna(axis=0, subset=['geometry'])
    save_clusters(clusters=clusters, out_path=clusters_out)
    
    print('\t\tDone')
    print(f'\nDone {country}')
    
    return clusters


def clip_raster(raster, boundary, boundary_layer=None):
    """
    Clip the raster to the given administrative boundary.

    Parameters
    ----------
    raster: string, pathlib.Path or rasterio.io.DataSetReader
        Location of or already opened raster.
    boundary: string, pathlib.Path or geopandas.GeoDataFrame
        The poylgon by which to clip the raster.
    boundary_layer: string, optional
        For multi-layer files (like GeoPackage), specify the layer to be used.


    Returns
    -------
    tuple
        Three elements:
            clipped: numpy.ndarray
                Contents of clipped raster.
            affine: affine.Affine()
                Information for mapping pixel coordinates
                to a coordinate system.
            crs: dict
                Dict of the form {'init': 'epsg:4326'} defining the coordinate
                reference system of the raster.

    """

    if isinstance(raster, Path):
        raster = str(raster)
    if isinstance(raster, str):
        raster = rasterio.open(raster)

    crs = raster.crs
    
    if isinstance(boundary, Path):
        boundary = str(boundary)
    if isinstance(boundary, str):
        if '.gpkg' in boundary:
            driver = 'GPKG'
        else:
            driver = None  # default to shapefile
            boundary_layer = ''  # because shapefiles have no layers
    
        boundary = gpd.read_file(boundary, layer=boundary_layer, driver=driver)

    boundary = boundary.to_crs(crs=raster.crs)
    coords = [json.loads(boundary.to_json())['features'][0]['geometry']]

    # mask/clip the raster using rasterio.mask
    clipped, affine = mask(dataset=raster, shapes=coords, crop=True)

    return clipped, affine, crs


def create_clusters(raster, affine, crs):
    """
    Create a polygon GeoDataFrame from the given raster

    Parameters
    ----------
    raster: numpy.ndarray
        The raster data to use.
    affine: affine.Affine()
        Raster pixel mapping information.
    crs: dict
        Dict of the form {'init': 'epsg:4326'} defining the coordinate
        reference system to use.

    Returns
    -------
    clusters: geopandas.GeoDataFrame
        A GeoDataFrame with integer index and two columns:
        geometry contains the Shapely polygon representations
        raster_val contains the values from the raster

    """

    raster = raster.astype(np.float32)

    geoms = list(({'properties': {'raster_val': v}, 'geometry': s} 
                  for i, (s, v)
                  in enumerate(shapes(raster, mask=None, transform=affine))))

    clusters = gpd.GeoDataFrame.from_features(geoms)
    clusters.crs = crs

    return clusters


def filter_merge_clusters(clusters, max_block_size_multi=5, min_block_pop=50, buffer_amount=150):
    """
    The vectors created by create_clusters() are a single square for each raster pixel.
    This function does the follows:
    - Remove overly large clusters, caused by defects in the input raster.
    - Remove clusters with population below a certain threshold.
    - Buffer the remaining clusters and merge those that overlap.

    Parameters
    ----------
    clusters: geopandas.GeoDataFrame
        The unprocessed clusters created by create_clusters()
    max_block_size_multi: int, optional
        Remove clusters that are more than this many times average size. Default 5.
    min_block_pop: int, optional
        Remove clusters with below this population. Default 50.
    buffer_amount: int, optional
        Distance in metres by which to buffer the clusters before merging. Default 150.

    Returns
    -------
    clusters: geopandas.GeoDataFrame
        The processed clusters.
    """

    # remove blocks that are too big (basically artifacts)
    clusters['area'] = clusters.geometry.area
    clusters = clusters[clusters['area'] < clusters['area'].mean() * max_block_size_multi]

    # remove blocks with too few people
    clusters = clusters[clusters['raster_val'] > min_block_pop]

    # buffer outwards so that nearby blocks will overlap
    clusters['geometry'] = clusters.geometry.buffer(buffer_amount)

    # and dissolve the thousands of blocks into a single layer (with no attributes!)
    clusters['same'] = 1
    clusters = clusters.dissolve(by='same')

    # To get our attributes back, we convert the dissolves polygon into singleparts
    # This means each contiguous bubble becomes its own polygon and can store its own attributes
    clusters = clusters.explode()
    clusters = clusters.reset_index()

    # no longer needed in GeoPandas >= 0.4.0
    # clusters['geometry'] = clusters[0]
    # clusters = gpd.GeoDataFrame(clusters)
    # clusters.crs = crs

    clusters = clusters.drop(columns=['same', 'level_1', 'raster_val'])  # raster_val is no longer meaningful
    
    # And then add the polygon's area back to its attributes
    clusters["area"] = clusters['geometry'].area
    clusters = clusters.to_crs(epsg = 4326)

    return clusters


def add_raster_layer(clusters, raster, operation, col_name, affine=None, crs=None):
    """
    The filter_merge_clusters() process loses the underlying raster values.
    So we need to use rasterstats.zonal_stats() to get it back.

    Parameters
    ----------
    clusters: geopandas.GeoDataFrame
        The processed clusters.
    raster: str, pathlib.Path or numpy.ndarray
        Either a path to the raster, or an already imported numpy.ndarray with the data.
    operation: str
        The operation to perform when extracting the raster data.
        Either 'sum', 'max', or 'mean'
    col_name: str
        Name of the column to add.
    affine: affine.Affine(), optional
        If a numpy ndarray is passed above, the affine is also needed.
    crs: proj.crs, optional
        Override raster's reported crs

    Returns
    -------
    clusters: geopandas.GeoDataFrame
        The processed clusters with new column.
    """
    if isinstance(raster, Path):
        raster = str(raster)
    if isinstance(raster, str):
        # rasterstats doesn't check for same CRS
        # Throws memory error if don't ensure they are same
        if not crs:
            crs = rasterio.open(raster).crs
        clusters_proj = clusters.to_crs(crs)
        stats = zonal_stats(clusters_proj, raster, stats=operation, nodata=0)

        clusters_proj[col_name] = [x[operation] for x in stats]

        clusters = clusters_proj.to_crs(clusters.crs)

        return clusters

    else:
        raise NotImplementedError('Only implemented for path input.')


def add_vector_layer(clusters, vector, operation, col_name, shape, affine, raster_crs):
    """
    Use a vector containing grid infrastructure to determine
    each cluster's distance from the grid.

    Parameters
    ----------
    clusters: geopandas.GeoDataFrame
        The processed clusters.
    vector: str, pathlib.Path or geopandas.GeoDataFrame
        Path to or already imported grid dataframe.
    operation: str
        Operation to perform in extracting vector data.
        Currently only 'distance' supported.
    shape: tuple
        Tuple of two integers representing the shape of the data
        for rasterizing grid. Sould match the clipped raster.
    affine: affine.Affine()
        As above, should match the clipped raster.

    Returns
    -------
    clusters: geopandas.GeoDataFrame
        The processed clusters with new column.

    """

    if isinstance(vector, Path):
        vector = str(vector)
    if isinstance(vector, str):
        vector = gpd.read_file(vector)

    vector = vector.to_crs(crs=raster_crs)
    clusters = clusters.to_crs(crs=raster_crs)

    if operation == 'distance':
        vector = vector.loc[vector['geometry'].length > 0]

        grid_raster = rasterize(vector.geometry, out_shape=shape, fill=1,
                                default_value=0, all_touched=True, transform=affine)
        dist_raster = ndimage.distance_transform_edt(grid_raster) * affine[0]

        dists = zonal_stats(vectors=clusters, raster=dist_raster, affine=affine, stats='min', nodata=1e9)
        clusters[col_name] = [x['min'] for x in dists]

        return clusters.to_crs(epsg=4326)

    else:
        raise NotImplementedError('Currently only "distance" is supported as an argument for operations.')


def fix_column(clusters, col_name, factor=1, minimum=0, maximum=None, no_value=None, per_capita=False):
    """

    """

    # multiply the column by a fixed factor
    if factor != None and factor != 1:
        clusters[col_name] = clusters[col_name] * factor

    # remove negative values
    if minimum != None:
        clusters.loc[clusters[col_name] < minimum, col_name] = minimum

    if per_capita:
        clusters[col_name] = clusters[col_name] / clusters['pop']

    # apply a cutoff maximum value
    if maximum != None:
        if maximum == 'largest':
            limit = 2 * float(clusters.loc[clusters['pop'] == clusters['pop'].max(), col_name].tolist()[0])
            clusters.loc[clusters[col_name] > limit, col_name] = limit
        
        else:
            raise NotImplementedError('maximum only implemented for "largest".')

    # replace nan values
    if no_value != None:
        if no_value == 'median':
            replace = {col_name: clusters[col_name].median()}
            clusters = clusters.fillna(value=replace)

        else:
            raise NotImplementedError('no_value only implemented for "median".')

    return clusters



def save_clusters(clusters, out_path):
    """
    Convert to EPSG:4326 and save to the specified file.
    clusters: geopandas.GeoDataFrame
        The processed clusters.
    out_path: str or pathlib.Path
        Where to save the clusters file.
    """

    if isinstance(out_path, Path):
        out_path = str(out_path)
    if '.gpkg' in out_path:
        driver = 'GPKG'
    elif '.geojson' in out_path or '.json' in out_path:
        driver='GeoJSON'
    else:
        driver = None

    clusters = clusters.to_crs(epsg=4326)
    clusters.to_file(out_path, driver=driver)
