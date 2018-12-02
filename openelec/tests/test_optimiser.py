from openelec import util
from pathlib import Path
import geopandas as gpd
from collections import defaultdict


TEST_DATA = Path('test_data')
BUILDINGS = TEST_DATA / 'Nakiu.geojson'

def test_clip_raster():
	villages = util.village_centroids(TEST_DATA)
	assert isinstance(villages, defaultdict)
