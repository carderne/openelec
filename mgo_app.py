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
                            ready_to_run=True, has_results=False,
                            latitude=latlong[0], longitude=latlong[1], minimum_area_m2='50', demand_multiplier='1',
                            price_pv_multiplier='0.25', price_wire='10', price_conn='100', price_maintenance='0.02',
                            years='10', max_tot_length='100000')

        # or if it's the run model button
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

            new_map, results, village = session['model'].run_model(latitude, longitude, minimum_area_m2, demand_multiplier, price_pv_multiplier,
                                                                   price_wire, price_conn, price_maintenance, years, max_tot_length)
            
            return render_template('index.html', map_file=new_map,
                            village_msg='You chose {}'.format(village), villages=session['villages'],
                            ready_to_run=True, has_results=True,
                            latitude=latitude, longitude=longitude, minimum_area_m2=minimum_area_m2, demand_multiplier=demand_multiplier,
                            price_pv_multiplier=price_pv_multiplier, price_wire=price_wire, price_conn=price_conn, price_maintenance=price_maintenance,
                            years=years, max_tot_length=max_tot_length,
                            connected=results['connected'], length=results['length'], capex=results['capex'], opex=results['opex'], income=results['income'], profit=results['profit'])

    return render_template('index.html', map_file='static/tz_overview.html',
                            village_msg='Choose here', villages=session['villages'],
                            ready_to_run=False, has_results=False)

if __name__ == '__main__':
    app.wsgi_app = SessionMiddleware(app.wsgi_app, session_opts)
    app.session_interface = BeakerSessionInterface()
    app.run(debug=True)

