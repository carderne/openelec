# model.py
#!python3

"""
model module for openelec.
Provides common functionality for LocalModel and NationalModel.
"""

from . import io


class Model:
    """
    Base class for NationalModel and LocalModel.
    """
        

    def __init__(self, data):
        """
        Initialise LocalModel object and read input data.

        Parameters
        ----------
        data : str, Path or GeoJSON-like
            Fiona-readable file or GeoJSON representation of polygon features.
        """

        self.data = data
        self.targets = io.read_data(data=self.data)

        self.x_mean = None
        self.y_mean = None
        self.origins = None

        self.network = None
        self.network_out = None

        self.nodes = None
        self.targets_out = None


    def setup(self, sort_by=None, **kwargs):
        """
        Basic set up on target features.

        Parameters
        ----------
        min_area : int, optional (default 20.)
            Area in m2, below which features will be excluded.
        **kwargs : **dict
            see baseline()
        """

        if sort_by:
            # Sort with largest first
            self.targets = self.targets.sort_values(sort_by, ascending=False)

        self.baseline(**kwargs)
        self.x_mean = self.targets.geometry.centroid.x.mean()
        self.y_mean = self.targets.geometry.centroid.y.mean()

        self.targets = self.targets.reset_index().drop(columns=['index'])


    def baseline(self):
        raise NotImplementedError('This method should always be over-ridden.')


    def save_to_path(self, path):
        """
        Save the resultant network and buildings to GeoJSON files.
        spatialise() must have been run before.

        Parameters
        ---------
        path : str, Path
            Path to a directory to create GeoJSON files.
            Will be created if needed, will not prompt on overwrite.
        """

        io.save_to_path(path, network_out=self.network_out, targets_out=self.targets_out)

    def results_as_geojson(self, network_columns=None, targets_columns=None):
        """
        Convert all model output to GeoJSON.
        """

        network_geojson = io.geojsonify(self.network_out, property_cols=network_columns)
        targets_geojson = io.geojsonify(self.targets_out, property_cols=targets_columns)

        return network_geojson, targets_geojson
