# minigrid-optimiser
[![Build Status](https://travis-ci.org/carderne/minigrid-optimiser.svg?branch=master)](https://travis-ci.org/carderne/minigrid-optimiser)

A tool for optimising rural [mini-grid systems](https://energypedia.info/wiki/Mini_Grids) using OpenStreetMap building data and a minimum spanning tree approach to network optimisation. 

Provides model features through a simple API, as well as a basic Flask web app.

See the blog post here for a general overview of the model development (probably out of date): [https://rdrn.me/flask-optimize-minigrid/](https://rdrn.me/flask-optimize-minigrid/)

Examples
--------------

**Basic API**

Have a look at the example Jupyter Notebook for a quick overview of the main API features:

[minigrid-optimiser.ipynb](http://nbviewer.jupyter.org/github/carderne/minigrid-optimiser/blob/master/minigrid-optimiser.ipynb)

**Web App usage**

[![Web App demo](https://thumbs.gfycat.com/CarefreeRemarkableAardwolf-size_restricted.gif)](https://gfycat.com/CarefreeRemarkableAardwolf)

Installation
--------

**Requirements**

minigrid-optimiser requires Python >= 3.5 with the following packages installed:

- ``flask`` >= 1.0.2 (only for the web app)
- ``numpy`` >= 1.14.2
- ``pandas`` >= 0.22.0
- ``geopandas`` >= 0.4.0 (0.4.0 had API breaking changes so this version is needed)
- ``shapely`` >= 1.6.4
- ``astroML`` >= 0.3
- ``scipy`` >= 1.0.0
- ``scikit-learn`` == 0.17.1 (later versions are not compatible with astroML)

**Install**

Downloads or clone the repository:

``git clone https://github.com/carderne/minigrid-optimiser.git``

Then run ``jupyter notebook`` and open ``minigrid-optimiser.ipynb`` to go over the main model usage and API.

**Web App**

To use the web app, run the following from the main directory:

```
cd mgo
python3 mgo_app.py
```

and navigate to http://127.0.0.1:5000/ in a browser to access the web app.