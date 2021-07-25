from flask import Flask, render_template, request
from flask_pymongo import PyMongo
import os
import requests
# from configure import FOURSQUARE_CLIENT_ID, FOURSQUARE_CLIENT_SECRET, SECRET_KEY, MONGO_URI



app = Flask(__name__)
app.secret_key = SECRET_KEY

app.config["MONGO_URI"] = MONGO_URI
mongo = PyMongo(app)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/submit")
def submit():
    return render_template("submit.html")


@app.route("/search-submit")
def search_submit():
    user_ip = request(request.remote_addr)
    response_ll = requests.get("http://ip-api.com/json/" + user_ip).json()
    lat = str(response_ll["lat"])
    lon = str(response_ll["lon"])
    print(lat + "," + lon)
    query = request.args.get("loc")
    params = {
        "client_id": FOURSQUARE_CLIENT_ID,
        "client_secret": FOURSQUARE_CLIENT_SECRET,
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


if __name__ == "__main__":
    app.run(debug=True)