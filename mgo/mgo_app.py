from flask import Flask, render_template, request, jsonify
from mgo import MgoModel
import mgo_utils


# create new app and give some folders (not sure if the folders are necessary)
app = Flask(__name__)       
app.config['UPLOAD_FOLDER'] = 'uploads'
app._static_folder = 'static'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/_get_village_list')
def get_village_list():
    # get village names and centroids
    villages = mgo_utils.village_centroids('uploads')

    return jsonify(villages=villages)


@app.route('/_run_model')
def run_model():
    name = request.args.get('name', 0, type=str)
    gen_lat = request.args.get('gen_lat', 0, type=float)
    gen_lng = request.args.get('gen_lng', 0, type=float)
    minimum_area_m2 = request.args.get('minimum_area_m2', 0, type=int)
    demand = request.args.get('demand', 0, type=int)
    tariff = request.args.get('tariff', 0, type=float)
    gen_cost = request.args.get('gen_cost', 0, type=int)
    cost_wire = request.args.get('cost_wire', 0, type=int)
    cost_connection = request.args.get('cost_connection', 0, type=int)
    opex_ratio = request.args.get('opex_ratio', 0, type=int)
    years = request.args.get('years', 0, type=int)
    discount_rate = request.args.get('discount_rate', 0, type=int)
    max_tot_length = request.args.get('max_tot_length', 0, type=int)

    model = MgoModel('')
    model.set_village(name, 'uploads')
    model.set_latlng(gen_lat, gen_lng)
    results, network, buildings = model.run_model(minimum_area_m2, demand, tariff, gen_cost, cost_wire,
                                                        cost_connection, opex_ratio, years, discount_rate, max_tot_length)

    return jsonify(results=results, network=network, buildings=buildings)

if __name__ == '__main__':
    app.run(debug=True)
