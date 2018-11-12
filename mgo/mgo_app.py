"""
Flask app with API points
"""

from flask import Flask, render_template, request, jsonify
import mgo


# create new app and give some folders (not sure if the folders are necessary)
app = Flask(__name__)
uploads = 'uploads'
app.config['UPLOAD_FOLDER'] = uploads
app._static_folder = 'static'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/_get_village_list')
def get_village_list():
    # get village names and centroids
    villages = mgo.village_centroids(uploads)

    return jsonify(villages=villages)


@app.route('/_run_model')
def run_model():
    # load the relevant buildings file
    buildings = mgo.load_buildings(village=request.args.get('name', 0, type=str),
                                   file_dir=uploads,
                                   min_area=request.args.get('min_area', 0, type=int))

    # create the network and nodes for this village
    network, nodes = mgo.create_network(buildings,
                                        gen_lat=request.args.get('gen_lat', 0, type=float),
                                        gen_lng=request.args.get('gen_lng', 0, type=float),
                                        max_length=request.args.get('max_length', 0, type=int))

    # run model and get summary results
    results, network, nodes = mgo.run_model(network, nodes,
                                            demand=request.args.get('demand', 0, type=int),
                                            tariff=request.args.get('tariff', 0, type=float),
                                            gen_cost=request.args.get('gen_cost', 0, type=int),
                                            cost_wire=request.args.get('cost_wire', 0, type=int),
                                            cost_connection=request.args.get('cost_connection', 0, type=int),
                                            opex_ratio=request.args.get('opex_ratio', 0, type=int),
                                            years=request.args.get('years', 0, type=int),
                                            discount_rate=request.args.get('discount_rate', 0, type=int))

    # convert results to GeoDataFrames
    network, buildings = mgo.network_to_spatial(buildings, network, nodes)

    # and then convert these to GeoJSON
    network = mgo.gdf_to_geojson(network)
    buildings = mgo.gdf_to_geojson(buildings, property_cols=['area'])

    return jsonify(results=results, network=network, buildings=buildings)

if __name__ == '__main__':
    app.run(debug=True)
