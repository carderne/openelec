import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString
import geopandas as gpd
import os.path
from collections import defaultdict

def village_centroids(villages_path):

	villages = defaultdict(tuple)

	for file in os.listdir(villages_path):
		if file.endswith('.shp'):

			name = os.path.splitext(file)[0]
			#villages.append(name)

			gdf = gpd.read_file(os.path.join(villages_path, file))
			lng = gdf.geometry.centroid.x.mean()
			lat = gdf.geometry.centroid.y.mean()
			#centroids.append((x, y))

			villages[name] = {'lat': lat, 'lng': lng}

	return villages