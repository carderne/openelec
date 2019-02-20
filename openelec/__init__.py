#!python3
# __init__.py

"""openelec package contains the following modules:
- clustering
- model
- local
- national
- io
- network
- prioritise
- util

GPL-3.0 (c) Chris arderne
"""

__version__ = "0.0.4"

EPSG4326 = {"init": "epsg:4326"}
# This is the Africa Albers Equal Area Conic EPSG: 102022
EPSG102022 = """+proj=aea
                +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25
                +x_0=0 +y_0=0
                +ellps=WGS84 +datum=WGS84 +units=m +no_defs"""
