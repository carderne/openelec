# openelec
[![Build Status](https://travis-ci.org/carderne/openelec.svg?branch=master)](https://travis-ci.org/carderne/openelec) [![PyPI version](https://badge.fury.io/py/openelec.svg)](https://badge.fury.io/py/openelec) 

openelec is a general tool for finding opportunities in electricity access. Able to create national-level plans for achieving universal electricity access, as well as optimise town/village-level mini-grid, densification and standalone systems. In addition, the tool provides functionality to find private-sector off-grid opportunities.

The library has a currently not very user-friendly Python API for scripting/notebook use.  
There is also a [demonstration web interface running here](https://openelec.me/) (static front-end on AWS S3 with serverless backend on Lambda)


### National-level

A tool for modelling the optimal pathways to improving electricity access.  
Described in my blog post here: [Modelling the optimum way to achieve universal electrification](https://rdrn.me/modelling-universal-electrification/)

### Town-level

A tool for optimising rural [mini-grid systems](https://energypedia.info/wiki/Mini_Grids) and LV networks using OpenStreetMap building data and a minimum spanning tree approach to network optimisation.  
Described in my blog post here: [A Flask app for mini-grid planning with a cost-optimised spanning tree](https://rdrn.me/flask-optimize-minigrid/)

**Web App usage (click to get proper resolution)**

[![Web App demo](https://thumbs.gfycat.com/FocusedMasculineLamb-size_restricted.gif)](https://openelec.me/index.html#modalVideo)

Model usage
--------

To get to grips with the API and steps in the model, open the Jupyter notebook `example.ipynb`. This repository  includes the input data needed to do a test run for Lesotho, so it should be a matter of opening the notebook and running all cells.

It also includes test data for a small village in central Lesotho to run the local version of the model.

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

Download or clone the repository and install the required packages (preferably in a virtual environment):

```
git clone https://github.com/carderne/openelec.git
cd gridfinder
pip install -r requirements.txt
```
You can run ```./test.sh``` in the directory, which will do an entire run through using the test data and confirm whether everything is set up properly.