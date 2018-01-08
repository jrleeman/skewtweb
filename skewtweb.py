from flask import Flask, render_template, send_file, redirect, url_for, request, Markup
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, TextField
from wtforms.ext.dateutil.fields import DateTimeField
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired
from datetime import datetime
from io import BytesIO
import metpy.calc as mpcalc
from metpy.plots import add_metpy_logo, SkewT, Hodograph
from metpy.units import units
import matplotlib.pyplot as plt
import numpy as np
from siphon.simplewebservice.wyoming import WyomingUpperAir
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from functools import lru_cache

app = Flask(__name__)
app.secret_key = 'NTOBiFxcjaehKa9nvgTmv5dslPUay7l4QDauEGIV3pSwpZKhpFGqJzestVyGODNT7BL8mauL38xyzgukYV3cIMix9eO8Jgb3bhvo'


class DataSelectionForm(FlaskForm):
    timefield = SelectField('Time',
                                choices=[(0, '00 Z'), (12, '12 Z')],
                                default=0)
    regionfield = SelectField('Region',
                                choices=[('naconf', 'North America'),
                                         ('samer', 'South America'),
                                         ('pac', 'South Pacific'),
                                         ('nz', 'New Zealand'),
                                         ('ant', 'Antarctica'),
                                         ('np', 'Arctic'),
                                         ('europe', 'Europe'),
                                         ('africa', 'Africa'),
                                         ('seasia', 'Southeast Asis'),
                                         ('mideast', 'Mideast')],
                                         default='naconf')
    datefield = DateField(default=datetime.utcnow())
    stationfield = TextField('Station', default='OUN')



@app.route('/')
def home():
    return render_template('index.html')


@app.route('/skewt', methods=['GET', 'POST'])
def skewtpage():

    dataselectionform = DataSelectionForm()
    dtstring = datetime.strftime(dataselectionform.datefield.data, '%Y%m%d')
    datareqstring = '?date={}&time={}&region={}&station={}'.format(dtstring, dataselectionform.timefield.data,
                                                                   dataselectionform.regionfield.data,
                                                                   dataselectionform.stationfield.data)
    print(datareqstring)
    return render_template("skewt.html", data_selector_form=dataselectionform,
                           datarequest=datareqstring)

@lru_cache(maxsize=32)
def get_sounding_data(date, region, station):
    return WyomingUpperAir.request_data(date, station, region=region)

@app.route('/skewt/skewt_fig')
def make_skewt():
    # Get the data
    date = request.args.get('date')
    time = request.args.get('time')
    region = request.args.get('region')
    station = request.args.get('station')
    date = datetime.strptime(date, '%Y%m%d')
    date = datetime(date.year, date.month, date.day, int(time))
    df = get_sounding_data(date, region, station)
    p = df['pressure'].values * units(df.units['pressure'])
    T = df['temperature'].values * units(df.units['temperature'])
    Td = df['dewpoint'].values * units(df.units['dewpoint'])
    u = df['u_wind'].values * units(df.units['u_wind'])
    v = df['v_wind'].values * units(df.units['v_wind'])

    # Make the Skew-T
    fig = plt.figure(figsize=(9, 9))
    add_metpy_logo(fig, 115, 100)
    skew = SkewT(fig, rotation=45)

    # Plot the data using normal plotting functions, in this case using
    # log scaling in Y, as dictated by the typical meteorological plot
    skew.plot(p, T, 'tab:red')
    skew.plot(p, Td, 'tab:green')
    skew.plot_barbs(p, u, v)
    skew.ax.set_ylim(1000, 100)
    skew.ax.set_xlim(-40, 60)

    # Calculate LCL height and plot as black dot
    lcl_pressure, lcl_temperature = mpcalc.lcl(p[0], T[0], Td[0])
    skew.plot(lcl_pressure, lcl_temperature, 'ko', markerfacecolor='black')

    # Calculate full parcel profile and add to plot as black line
    prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
    skew.plot(p, prof, 'k', linewidth=2)

    # Shade areas of CAPE and CIN
    skew.shade_cin(p, T, prof)
    skew.shade_cape(p, T, prof)

    # An example of a slanted line at constant T -- in this case the 0
    # isotherm
    skew.ax.axvline(0, color='c', linestyle='--', linewidth=2)

    # Add the relevant special lines
    skew.plot_dry_adiabats()
    skew.plot_moist_adiabats()
    skew.plot_mixing_lines()

    canvas = FigureCanvas(fig)
    img = BytesIO()
    fig.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

@app.route('/skewt/hodograph_fig')
def make_hodograph():
    # Get the data
    date = request.args.get('date')
    time = request.args.get('time')
    region = request.args.get('region')
    station = request.args.get('station')
    date = datetime.strptime(date, '%Y%m%d')
    date = datetime(date.year, date.month, date.day, int(time))
    df = get_sounding_data(date, region, station)
    p = df['pressure'].values * units(df.units['pressure'])
    T = df['temperature'].values * units(df.units['temperature'])
    Td = df['dewpoint'].values * units(df.units['dewpoint'])
    u = df['u_wind'].values * units(df.units['u_wind'])
    v = df['v_wind'].values * units(df.units['v_wind'])

    # Make the Hodograph
    # Create a new figure. The dimensions here give a good aspect ratio
    fig = plt.figure(figsize=(4, 4))
    ax_hod = plt.subplot(1, 1, 1)
    h = Hodograph(ax_hod, component_range=80.)
    h.add_grid(increment=20)
    h.plot_colormapped(u, v, np.hypot(u, v))

    canvas = FigureCanvas(fig)
    img = BytesIO()
    fig.savefig(img)
    img.seek(0)
    return send_file(img, mimetype='image/png')

if __name__ == "__main__":
    app.run(port=5000, debug=True)
