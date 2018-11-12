from mgo import mgo
from pathlib import Path
import geopandas as gpd
from collections import defaultdict


TEST_DATA = Path('mgo/uploads')
BUILDINGS = TEST_DATA / 'Nakiu.geojson'

def test_clip_raster():
	villages = mgo.village_centroids(TEST_DATA)
	assert isinstance(villages, defaultdict)
