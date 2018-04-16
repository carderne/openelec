import os
from flask import Flask, session, render_template, request
from flask.sessions import SessionInterface
from beaker.middleware import SessionMiddleware
from mgo_model import MgoModel

# options for the beaker session
session_opts = {
    'session.type': 'file',
    'session.data_dir': './cache',
}


# honestly not sure how this works
class BeakerSessionInterface(SessionInterface):
    def open_session(self, app, request):
        session = request.environ['beaker.session']
        return session

    def save_session(self, app, session, response):
        session.save()

# create new app and give some folders (not sure if the folders are necessary)
app = Flask(__name__)       
app.config['UPLOAD_FOLDER'] = 'uploads'
app._static_folder = 'static'
app.wsgi_app = SessionMiddleware(app.wsgi_app, session_opts)
app.session_interface = BeakerSessionInterface()

@app.route('/static/<path:filename>', methods=['GET', 'POST'])
def download(path, filename):
    return send_from_directory(directory=path, filename=filename)

# this function handles standard visits and all GET and POST methods at th top level URL
@app.route('/', methods=['GET', 'POST'])
def index():

    # if this session doesn't exist, we create it!
    if not session.has_key('session_dir'):

        # a personal folder for all maps created in this session
        session['session_dir'] = 'static/{}'.format(session['_creation_time'])
        os.mkdir(session['session_dir'])

        # just in case new village shapfiles have been added
        villages = []
        for file in os.listdir('uploads'):
            if file.endswith('.shp'):
                villages.append(os.path.splitext(file)[0])

        # and instantiate a personal MgoModel for this session
        session['villages'] = villages
        session['model'] = MgoModel(session['session_dir'])

    # clicking for generator location uses GET
    if request.method == 'GET':
        if request.args.get('lat'):
            latitude = request.args.get('lat')
            longitude = request.args.get('lng')
            
            village = session['model'].get_village()
            map_with_gen = session['model'].map_with_pv(latitude, longitude)
            return render_template('index.html', map_file=map_with_gen,
                            village_msg='You chose {}'.format(village), villages=session['villages'],
                            show_params=True, show_results=False,
                            minimum_area_m2="50", demand_multiplier="0.5",
                            price_pv_multiplier="0.5", price_wire="10", price_conn="100", price_maintenance="0.01",
                            years="10", max_tot_length="10000")

    # both buttons use the POST method
    if request.method == 'POST':

        # check if this is the choose village button
        if 'choose' in request.form:
            # quick check to make sure they didn't click with the dropdown on an invalid menu item
            villages = session['villages']
            village = request.form['village']
            if village in villages:
                empty_map = 'static/empty_map_{}.html'.format(village)
                # and set hte MgoModel to the correct village
                latlong = session['model'].set_village(village)

                # render with the empty_map, default parameter values and no results values

                # add an if in index.html to not display any results if there aren't any results
                return render_template('index.html', map_file=empty_map,
                            village_msg='You chose {}'.format(village), villages=villages,
                            show_params=False, show_results=False)

        # or if it's the run model button
        if 'minimum_area_m2' in request.form:
            minimum_area_m2 = request.form['minimum_area_m2']
            demand_multiplier = request.form['demand_multiplier']
            price_pv_multiplier = request.form['price_pv_multiplier']
            price_wire = request.form['price_wire']
            price_conn = request.form['price_conn']
            price_maintenance = request.form['price_maintenance']
            years = request.form['years']
            max_tot_length = request.form['max_tot_length']

            new_map, results, village, zipped = session['model'].run_model(minimum_area_m2, demand_multiplier, price_pv_multiplier,
                                                                   price_wire, price_conn, price_maintenance, years, max_tot_length)
            
            return render_template('index.html', map_file=new_map,
                            village_msg='You chose {}'.format(village), villages=session['villages'],
                            show_params=True, show_results=True,
                            minimum_area_m2=minimum_area_m2, demand_multiplier=demand_multiplier,
                            price_pv_multiplier=price_pv_multiplier, price_wire=price_wire, price_conn=price_conn, price_maintenance=price_maintenance,
                            years=years, max_tot_length=max_tot_length,
                            connected=results['connected']-1, length=results['length'], capex=results['capex'], opex=results['opex'], income=results['income'], profit=results['profit'],
                            zipped=zipped)

    return render_template('index.html', map_file='static/tz_overview.html',
                            village_msg='Choose here', villages=session['villages'],
                            show_params=False, show_results=False)

if __name__ == '__main__':
    app.run(debug=True)

