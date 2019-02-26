from openelec import clustering

import numpy as np
from affine import Affine
import rasterio
from pathlib import Path

TEST_DATA = Path("test_data")
TEST_OUTPUT = Path("test_output")

RASTER_FILE = TEST_DATA / "ghs.tif"
BOUNDARY_FILE = TEST_DATA / "gadm.gpkg"


def test_clip_raster():
    clipped, affine, crs = clustering.clip_raster(RASTER_FILE, BOUNDARY_FILE)
    assert isinstance(clipped, np.ndarray)
    assert isinstance(affine, Affine)
    assert isinstance(crs, rasterio.crs.CRS)
