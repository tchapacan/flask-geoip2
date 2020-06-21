import argparse
from functools import reduce
import gzip
import json
import requests
import logging

from flask import Flask, g, jsonify, request
import geoip2.database
import geoip2.errors


DB_FILE_LOCATION = 'data/GeoLite2-City.mmdb'
DB_FILE_URL = 'http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz'

JSON_MAPPING = {
        'country_name': 'country.name', 
        'longitude': 'location.longitude', 
        'zip_code': 'postal.code', 
        'time_zone': 'location.time_zone', 
        'region_code': 'subdivisions.most_specific.iso_code', 
        'country_code': 'country.iso_code', 
        'latitude': 'location.latitude', 
        'city': 'city.name', 
        'region_name': 'subdivisions.most_specific.name'
    }

# I have no idea what these are fiou
METRO_CODE = 0
CODE = 200

app = Flask(__name__)

def setup_logging(loglevel):
    logformat = "%(asctime)s: %(message)s"
    if loglevel:
        logging.basicConfig(level=logging.DEBUG,format=logformat)
    else:
        logging.basicConfig(level=logging.INFO,format=logformat)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Start a the flask server of the geoip project.')
    parser.add_argument('-d','--debug', action='store_true', help='Enable debugging')
    parser.add_argument('-f','--fresh', action='store_true', help='Download a fresh copy of the database')
    parser.add_argument('-o','--download', action='store_true', help='Only download the database - don\'t start the app')
    parser.add_argument("-v", "--verbose", action='store_true', help="increase output verbosity")

    return parser.parse_args()

def download_fresh_db():
    app.logger.info("downloading fresh database from: {}".format(DB_FILE_URL))
    req = requests.get(DB_FILE_URL, stream=True)
    gzip_file_location = "{}.gz".format(DB_FILE_LOCATION)

    with open(gzip_file_location,'wb') as f:
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()

    app.logger.info("decompressing database file...")
    with open(DB_FILE_LOCATION, 'wb') as f:
        with gzip.open(gzip_file_location, 'rb') as g:
            f.write(g.read())

def get_db_reader():
    reader = getattr(g, '_db_reader', None)
    if reader is None:
        app.logger.info("opening connection to database")
        reader = geoip2.database.Reader(DB_FILE_LOCATION)
    return reader

@app.route('/geoip/')
@app.route('/geoip/<ip_address>')
def geoip(ip_address=None):
    ip = ip_address if ip_address else request.remote_addr
    try:
        app.logger.info("looking up IP address: {}".format(ip))
        geoip_reader = get_db_reader()
        result = geoip_reader.city(ip)
        response = {}
        for key, value in JSON_MAPPING.items():
            try:
                response[key] = reduce(getattr, value.split('.'), result)
            except AttributeError:
                response[key] = ''
        response['ip'] = ip
        response['metro_code'] = METRO_CODE
        response['code'] = CODE
        app.logger.info("returning response: \n{}".format(json.dumps(response,indent=2)))
        return jsonify(**response)
    except geoip2.errors.AddressNotFoundError as e:
        app.logger.warning("Unable find ip address: {}".format(e))
        return jsonify({'error': {'message': e.message}})

if __name__ == '__main__':
    args = parse_arguments()
    setup_logging(args.verbose)

    if args.fresh or args.download:
        download_fresh_db()

    if not args.download:
        app.run(debug=args.debug)
