from flask import Flask, render_template, request, jsonify, url_for, redirect
from flask_wtf import FlaskForm
from flask_bootstrap import Bootstrap
from wtforms import RadioField, SubmitField
from wtforms.validators import DataRequired
from flask_pymongo import PyMongo
import os
import requests
# from configure import FOURSQUARE_CLIENT_ID, FOURSQUARE_CLIENT_SECRET, SECRET_KEY, MONGO_URI, GOOGLE_API_KEY, MY_IP
import datetime as dt
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', SECRET_KEY)

bootstrap = Bootstrap(app)

mongo = PyMongo(app, uri=os.environ.get('MONGO_URI', MONGO_URI))
db = mongo.db


class SubmitDataForm(FlaskForm):
    busyness = RadioField("Busyness Level", choices=["Dead", "Unbusy", "Normal", "Slightly Busy", "Very Busy"], validators=[DataRequired()])


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/submit")
def submit():
    return render_template("submit.html")


@app.route("/search-find")
def search_find():
    query = request.args.get("loc")
    if query != "":
        GOOGLE_GEOCODE_API_EP = "https://maps.googleapis.com/maps/api/geocode/json?"
        params_geocode = {
            "address": query,
            "key": os.environ.get('GOOGLE_API_KEY', GOOGLE_API_KEY)
        }
        response_geocode = requests.get(GOOGLE_GEOCODE_API_EP, params=params_geocode)
        lat = str(response_geocode.json()["results"][0]["geometry"]["location"]["lat"])
        lon = str(response_geocode.json()["results"][0]["geometry"]["location"]["lng"])
    else:
        if 'X-Forwarded-For' in request.headers:
            proxy_data = request.headers['X-Forwarded-For']
            ip_list = proxy_data.split(',')
            user_ip = ip_list[0]
        else:
            user_ip = request.remote_addr
            # user_ip = MY_IP # for testing
        response_ll = requests.get("http://ip-api.com/json/" + user_ip).json()
        lat = str(response_ll["lat"])
        lon = str(response_ll["lon"])
    params = {
        "client_id": os.environ.get("FOURSQUARE_CLIENT_ID", FOURSQUARE_CLIENT_ID),
        "client_secret": os.environ.get("FOURSQUARE_CLIENT_SECRET", FOURSQUARE_CLIENT_SECRET),
        "ll": lat + "," + lon,
        "radius": 5000,
        "limit": 50,
        "categoryId": "52f2ab2ebcbc57f1066b8b46,4bf58dd8d48988d118951735",
        "v": "20210701"
    }
    response = requests.get("https://api.foursquare.com/v2/venues/search", params=params)
    response.raise_for_status()
    data = response.json()
    grocery_stores_info = []
    now = dt.datetime.now()
    for store in data["response"]["venues"]:
        store_db = db.stores.find_one({'store_id': store["id"]})
        store_busyness = 0
        total_weight = 0
        total_data_sum = 0
        if store_db:  # store is already registered in database
            busyness_data = store_db["data"]
            for data_entry in busyness_data:
                entry_time = dt.datetime.strptime(data_entry[0], "%m/%d/%Y/%H/%M/%S")
                difference = round((now-entry_time).total_seconds()/60) #calculate difference in minutes between entrytime and now
                if difference > 720: #don't use submissions older than 720 minutes old
                    continue
                else:
                    entry_weight = calc_data_weight(difference)
                    total_weight += entry_weight
                    total_data_sum += entry_weight * data_entry[1]
            if total_data_sum == 0 or total_weight == 0:
                weighted_busyness_avg = -1
            else:
                weighted_busyness_avg = round(total_data_sum / total_weight)
        else:
            weighted_busyness_avg = -1
        store_info = (store["id"], store["name"], store["location"]["formattedAddress"], weighted_busyness_avg)
        grocery_stores_info.append(store_info)
    return render_template("search_find.html", stores=grocery_stores_info)


def calc_data_weight(time_diff):
    weight = pow(0.5, (time_diff / 360))
    return weight


@app.route("/search-submit")
def search_submit():
    if 'X-Forwarded-For' in request.headers:
        proxy_data = request.headers['X-Forwarded-For']
        ip_list = proxy_data.split(',')
        user_ip = ip_list[0]
    else:
        user_ip = request.remote_addr
        # user_ip = MY_IP # for testing
    response_ll = requests.get("http://ip-api.com/json/" + user_ip).json()
    lat = str(response_ll["lat"])
    lon = str(response_ll["lon"])
    query = request.args.get("loc")
    params = {
        "client_id": os.environ.get("FOURSQUARE_CLIENT_ID", FOURSQUARE_CLIENT_ID),
        "client_secret": os.environ.get("FOURSQUARE_CLIENT_SECRET", FOURSQUARE_CLIENT_SECRET),
        "ll": lat+","+lon,
        "query": query,
        "limit": 20,
        "categoryId": "52f2ab2ebcbc57f1066b8b46,4bf58dd8d48988d118951735",
        "v": "20210701"
    }
    response = requests.get("https://api.foursquare.com/v2/venues/search", params=params)
    response.raise_for_status()
    data = response.json()
    grocery_stores_info = []
    for store in data["response"]["venues"]:
        store_info = (store["id"], store["name"], store["location"]["formattedAddress"])
        grocery_stores_info.append(store_info)

    return render_template("search_submit.html", stores=grocery_stores_info)


@app.route("/submit-data/<string:id>/<string:name>/<string:address>", methods=["POST", "GET"])
def submit_data(id, name, address):
    addr_str = ""
    for item in address:
        if item != "'" and item != "[" and item != "]":
            addr_str+=item
    submit_data_form = SubmitDataForm()
    if submit_data_form.validate_on_submit():
        data = submit_data_form.busyness.data
        if data == "Dead":
            data_num = 1
        elif data == "Unbusy":
            data_num = 2
        elif data == "Normal":
            data_num = 3
        elif data == "Slightly Busy":
            data_num = 4
        else:
            data_num = 5
        store = db.stores.find_one({'store_id': id})
        cur_time = dt.datetime.now().strftime("%m/%d/%Y/%H/%M/%S")
        if not store: # this store is not yet in the database (first time data is being submitted)
            new_store = db.stores.insert_one({'store_id':id, 'name':name, 'address':addr_str, 'data':[(cur_time, data_num)]})
        else: # this store is already in database; need to append new data submission to data list
            data = store["data"]
            data.append((cur_time, data_num))
            db.stores.update_one({"store_id":id}, {"$set": {"data":data}})
        return redirect(url_for("submit"))
    return render_template("submit_data.html", form=submit_data_form, id=id, name=name, address=addr_str)


if __name__ == "__main__":
    app.run(debug=True)