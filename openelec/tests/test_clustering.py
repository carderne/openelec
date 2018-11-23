from openelec import clustering

import numpy as np
from affine import Affine
import rasterio
from pathlib import Path

TEST_DATA = Path('test_data')

RASTER_FILE = TEST_DATA / 'raster.tif'
BOUNDARY_FILE = TEST_DATA / 'boundary.gpkg'
BOUNDARY_LAYER = 'boundary'
CLIPPED_RASTER = TEST_DATA / 'clipped.tif'
GRID_FILE = TEST_DATA / 'grid.gpkg'
CLUSTERS_FILE = TEST_DATA / 'clusters.gpkg'

def test_clip_raster():
	clipped, affine, crs = clustering.clip_raster(RASTER_FILE, BOUNDARY_FILE, BOUNDARY_LAYER)
	assert isinstance(clipped, np.ndarray)
	assert isinstance(affine, Affine)
	assert isinstance(crs, rasterio.crs.CRS)

def test_clusters():
	clipped_dataset = rasterio.open(CLIPPED_RASTER)
	clipped = clipped_dataset.read()
	affine = clipped_dataset.transform
	crs = clipped_dataset.crs

	clusters = clustering.create_clusters(clipped, affine, crs)
	assert all(clusters.columns == ['geometry', 'raster_val'])
	assert all(clusters['geometry'].type == 'Polygon')
	assert clusters['raster_val'].dtype == float

	clusters = clustering.filter_merge_clusters(clusters)
	assert all(clusters.columns == ['area', 'geometry'])

	#clusters = clustering.cluster_pops(clusters, RASTER_FILE)
	#assert all(clusters.columns == ['area_m2', 'geometry', 'pop_sum'])

	#clusters = clustering.cluster_grid_distance(clusters, GRID_FILE, clipped[0].shape, affine)
	#assert all(clusters.columns == ['area_m2', 'geometry', 'pop_sum', 'grid_dist'])

	clustering.save_clusters(clusters, CLUSTERS_FILE)
	assert Path(CLUSTERS_FILE).is_file()
	