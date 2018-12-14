# openelec
[![Build Status](https://travis-ci.org/carderne/openelec.svg?branch=master)](https://travis-ci.org/carderne/openelec) [![PyPI version](https://badge.fury.io/py/openelec.svg)](https://badge.fury.io/py/openelec) 

openelec is a general tool for finding opportunities in electricity access. Able to create national-level plans for achieving universal electricity access, as well as optimise town/village-level mini-grid, densification and standalone systems. In addition, the tool provides functionality to find private-sector off-grid opportunities.

[Web interface running here](https://openelec.surge.sh/)
(If the server isn't running the interface will work but no data will load.)

### National-level

A tool for modelling the optimal pathways to improving electricity access. Described in my blog post here: [Modelling the optimum way to achieve universal electrification](https://rdrn.me/modelling-universal-electrification/)

### Town-level

A tool for optimising rural [mini-grid systems](https://energypedia.info/wiki/Mini_Grids) and LV networks using OpenStreetMap building data and a minimum spanning tree approach to network optimisation. Described in my blog post here: [A Flask app for mini-grid planning with a cost-optimised spanning tree](https://rdrn.me/flask-optimize-minigrid/)

**Web App usage (click to get proper resolution)**

[![Web App demo](https://thumbs.gfycat.com/FocusedMasculineLamb-size_restricted.gif)](https://gfycat.com/FocusedMasculineLamb)

Installation
--------

**Requirements**

openelec requires Python >= 3.5 with the following packages installed:

- ``flask`` >= 1.0.2 (only for the web app)
- ``numpy`` >= 1.14.2
- ``pandas`` >= 0.22.0
- ``geopandas`` >= 0.4.0 (0.4.0 had API breaking changes so this version is needed)
- ``shapely`` >= 1.6.4
- ``scipy`` >= 1.0.0
- ``scikit-learn`` >= 0.17.1

**Install with pip**

```
pip install openelec
```

**Install from GitHub**

Downloads or clone the repository:

```
git clone https://github.com/carderne/openelec.git
```

Then ``cd`` into the directory, and install the required packages into a virtual environment:

```
pip install -r requirements.txt
```

Then run ``jupyter notebook`` and open ``minigrid-optimiser.ipynb``  or `electrify.ipynb` to go over the main model usage and API.
