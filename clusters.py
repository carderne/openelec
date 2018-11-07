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


def clip_raster(raster, boundary):
	boundary = boundary.to_crs(crs=raster.crs)
	coords = [json.loads(boundary.to_json())['features'][0]['geometry']]

	# mask/clip the raster using rasterio.mask
	raster_clipped, raster_affine = mask(dataset=raster, shapes=coords, crop=True)

	return raster_clipped, raster_affine


def create_clusters(raster, affine, crs):
	geoms = list(({'properties': {'raster_val': v}, 'geometry': s} 
	              for i, (s, v)
	              in enumerate(shapes(raster, mask=None, transform=affine))))

	clusters = gpd.GeoDataFrame.from_features(geoms)
	clusters.crs = crs

	return clusters


def filter_merge_clusters(clusters, max_block_size_multi=5, min_block_pop=50, buffer_amount=150):
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
	clusters['geometry'] = clusters[0]
	clusters = clusters.drop(columns=['level_0', 'level_1', 0]) # shapefile doesn't like integer column name
	clusters = gpd.GeoDataFrame(clusters)
	clusters.crs = crs

	# And then add the polygon's area back to its attributes
	clusters["area_m2"] = clusters['geometry'].area

	return clusters


def cluster_pops(clusters, pop_raster, affine=None):
    # But we still need to get the population data back, so we join it with the original raster data
    # We take the sum of all population that lies underneath the polygon

    if type(pop_raster) == str:
    	pop_sums = zonal_stats(clusters, pop_raster, stats='sum')

    else:
    	pop_sums = zonal_stats(clusters, pop_raster, affine=affine, stats='sum', nodata=0)

    clusters['pop_sum'] = [x['sum'] for x in pop_sums]

    return clusters


def cluster_grid_distance(clusters, grid, shape, affine):
    grid = grid.to_crs(crs=clusters.crs)
    grid = grid.loc[grid['geometry'].length > 0]

    grid_raster = rasterize(grid.geometry, out_shape=shape, fill=1,
                            default_value=0, all_touched=True, transform=affine)
    dist_raster = ndimage.distance_transform_edt(grid_raster) * affine[0]

    dists = zonal_stats(vectors=clusters, raster=dist_raster, affine=affine, stats='min', nodata=1000)
    clusters['grid_dist'] = [x['min'] for x in dists]

    return clusters


if __name__ == '__main__':
	folder_input = Path('/home/chris/Documents/GIS')
	ghs_in = folder_input / 'GHS-POP/GHS_POP_GPW42015_GLOBE_R2015A_54009_250_v1_0.tif'
	clip_boundary = folder_input / 'gadm_uganda.gpkg'
	clip_boundary_layer = 'gadm36_UGA_0'
	grid_in = folder_input / 'uganda_grid.gpkg'
	clusters_out = folder_input / 'clusters.gpkg'

	print('Reading files...', end='', flush=True)
	pop = rasterio.open(str(ghs_in))
	adm = gpd.read_file(str(clip_boundary), layer=clip_boundary_layer, driver='GPKG')
	grid = gpd.read_file(str(grid_in))
	print('\t\tDone')

	print('Clipping raster...', end='', flush=True)
	pop_clipped, pop_affine = clip_raster(pop, adm)
	print('\t\tDone')

	print('Creating clusters...', end='', flush=True)
	pop_poly = create_clusters(pop_clipped, pop_affine, pop.crs)
	print('\t\tDone')

	print('Filtering and merging...', end='', flush=True)
	pop_poly = filter_merge_clusters(pop_poly)
	print('\tDone')

	print('Getting population...', end='', flush=True)
	pop_poly = cluster_pops(pop_poly, str(ghs_in))
	print('\t\tDone')

	print('Getting grid dists...', end='', flush=True)
	pop_poly = cluster_grid_distance(pop_poly, grid, pop_clipped[0].shape, pop_affine)
	print('\t\tDone')

	print(f'Saving to {str(clusters_out)}...', end='', flush=True)
	pop_poly = pop_poly.to_crs(epsg=4326)
	pop_poly.to_file(str(clusters_out), driver='GPKG')
	print('\t\tDone')
