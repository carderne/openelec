import os
from flask import Flask, render_template, request, send_from_directory
from mgo_model import MgoModel

model = MgoModel()

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['cpg', 'dbf', 'prj', 'shp', 'shx', 'qpg'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app._static_folder = 'static'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<path:filename>', methods=['GET', 'POST'])
def download(filename):
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], filename=filename)

@app.route('/', methods=['GET', 'POST'])
def display_map():

    if request.method == 'POST':
        if 'choose' in request.form:
            empty_map = model.display_empty_map(request.form['village'])
            return render_template('index.html', map_file=empty_map,
                           latitude='-9.6329', longitude='39.1897', minimum_area_m2='50', demand_multiplier='1',
                           price_pv_multiplier='0.25', price_wire='10', price_conn='100', price_maintenance='0.02',
                           years='10', max_tot_length='100000',
                           connected='', length='', capex='', opex='', income='', profit='', village_msg='You chose {}'.format(request.form['village']))

        if 'latitude' in request.form:
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            minimum_area_m2 = request.form['minimum_area_m2']
            demand_multiplier = request.form['demand_multiplier']
            price_pv_multiplier = request.form['price_pv_multiplier']
            price_wire = request.form['price_wire']
            price_conn = request.form['price_conn']
            price_maintenance = request.form['price_maintenance']
            years = request.form['years']
            max_tot_length = request.form['max_tot_length']

            new_map, zipped, msg, village = model.run_model(latitude, longitude, minimum_area_m2, demand_multiplier, price_pv_multiplier, price_wire, price_conn, price_maintenance, years, max_tot_length)
            return render_template('index.html', map_file=new_map,
                                   latitude=latitude, longitude=longitude, minimum_area_m2=minimum_area_m2, demand_multiplier=demand_multiplier,
                                   price_pv_multiplier=price_pv_multiplier, price_wire=price_wire, price_conn=price_conn, price_maintenance=price_maintenance,
                                   years=years, max_tot_length=max_tot_length,
                                   connected=msg[0], length=msg[1], capex=msg[2], opex=msg[3], income=msg[4], profit=msg[5], village_msg='You chose {}'.format(village))

    return render_template('index.html', map_file='static/all_tz.html',
                           latitude='-9.6329', longitude='39.1897', minimum_area_m2='60', demand_multiplier='1',
                           price_pv_multiplier='0.25', price_wire='10', price_conn='100', price_maintenance='0.02',
                           years='10', max_tot_length='100000',
                           connected='', length='', capex='', opex='', income='', profit='', village_msg='Choose here')



if __name__ == "__main__":
    app.run(host='localhost')

