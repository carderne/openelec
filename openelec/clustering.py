"""
clusters module for electrification-planner

Provides functions to read in a raster population dataset
and convert to discrete vector polgons, each with a set
population value. Additionally calculate each polygon's
distance from a provided grid infrastructure vector. 
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


def clip_raster(raster, boundary, boundary_layer='gadm36_UGA_0'):
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


	geoms = list(({'properties': {'raster_val': v}, 'geometry': s} 
	              for i, (s, v)
	              in enumerate(shapes(raster, mask=None, transform=affine))))

	clusters = gpd.GeoDataFrame.from_features(geoms)
	clusters.crs = crs

	return clusters


# TODO Could instead filter at the raster stage?
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
	clusters['area_m2'] = clusters.geometry.area
	clusters = clusters[clusters['area_m2'] < clusters['area_m2'].mean() * max_block_size_multi]

	# remove blocks with too few people
	clusters = clusters[clusters['raster_val'] > min_block_pop]

	# buffer outwards so that nearby blocks will overlap
	clusters['geometry'] = clusters.geometry.buffer(buffer_amount)

	# and dissolve the thousands of blocks into a single layer (with no attributes!)
	clusters['same'] = 1
	clusters = clusters.dissolve(by='same')

	# To get our attributes back, we convert the dissolves polygon into singleparts
	# This means each contiguous bubble becomes its own polygon and can store its own attributes
	crs = clusters.crs
	clusters = clusters.explode()
	clusters = clusters.reset_index()

	# no longer needed in GeoPandas >= 0.4.0
	# clusters['geometry'] = clusters[0]
	# clusters = gpd.GeoDataFrame(clusters)
	# clusters.crs = crs

	clusters = clusters.drop(columns=['same', 'level_1', 'raster_val'])  # raster_val is no longer meaningful
	

	# And then add the polygon's area back to its attributes
	clusters["area_m2"] = clusters['geometry'].area

	return clusters


def cluster_pops(clusters, raster, affine=None):
	"""
	The filter_merge_clusters() process loses the underlying raster values.
	So we need to use rasterstats.zonal_stats() to get it back.

	Parameters
	----------
	clusters: geopandas.GeoDataFrame
		The processed clusters.
	raster: str, pathlib.Path or numpy.ndarray
		Either a path to the raster, or an already imported numpy.ndarray with the data.
	affine: affine.Affine(), optional
		If a numpy ndarray is passed above, the affine is also needed.

	Returns
	-------
	clusters: geopandas.GeoDataFrame
		The processed clusters.
	"""
	if isinstance(raster, Path):
		raster = str(raster)
	if isinstance(raster, str):
		pop_sums = zonal_stats(clusters, raster, stats='sum')

	else:
		pop_sums = zonal_stats(clusters, raster, affine=affine, stats='sum', nodata=0)

	clusters['pop_sum'] = [x['sum'] for x in pop_sums]

	return clusters


def cluster_grid_distance(clusters, grid, shape, affine):
	"""
	Use a vector containing grid infrastructure to determine
	each cluster's distance from the grid.

	Parameters
	----------
	clusters: geopandas.GeoDataFrame
		The processed clusters.
	grid: str, pathlib.Path or geopandas.GeoDataFrame
		Path to or already imported grid dataframe.
	shape: tuple
		Tuple of two integers representing the shape of the data
		for rasterizing grid. Sould match the clipped raster.
	affine: affine.Affine()
		As above, should match the clipped raster.

	Returns
	-------
	clusters: geopandas.GeoDataFrame
		The processed clusters.

	"""

	if isinstance(grid, Path):
		grid = str(grid)
	if isinstance(grid, str):
		grid = gpd.read_file(grid)

	grid = grid.to_crs(crs=clusters.crs)
	grid = grid.loc[grid['geometry'].length > 0]

	grid_raster = rasterize(grid.geometry, out_shape=shape, fill=1,
	                        default_value=0, all_touched=True, transform=affine)
	dist_raster = ndimage.distance_transform_edt(grid_raster) * affine[0]

	dists = zonal_stats(vectors=clusters, raster=dist_raster, affine=affine, stats='min', nodata=1000)
	clusters['grid_dist'] = [x['min'] for x in dists]

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
	else:
		driver = None

	clusters = clusters.to_crs(epsg=4326)
	clusters.to_file(out_path, driver=driver)
