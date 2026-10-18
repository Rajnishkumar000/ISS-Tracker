# app.py
from math import asin, cos, radians, sin, sqrt
import requests
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.secret_key = "secret" # flash() needs this to work because it store flash message as cookie in brower

db = SQLAlchemy(app)

class Sighting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    observer = db.Column(db.String(100), nullable=False)
    place = db.Column(db.String(100), nullable=False)
    observer_lat = db.Column(db.Float, nullable=False)
    observer_lon = db.Column(db.Float, nullable=False)
    iss_lat = db.Column(db.Float, nullable=False)
    iss_lon = db.Column(db.Float, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    visibility = db.Column(db.String(100), nullable=False)
    note = db.Column(db.String(255), default="")

def distance_km(lat1, lon1, lat2, lon2):
    """Haversine formula: distance between two points on Earth."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * 6371 * asin(sqrt(a)), 1)

def get_visibility_status(dist):
    if dist <= 1500:
        return "Clearly visible"
    elif dist <= 3000:
        return "Partly visible"
    return "Not visible"


def get_iss_position():
    """Returns (lat, lon) of the ISS, or None if the API fails."""
    try:
        data = requests.get("http://api.open-notify.org/iss-now.json", timeout=8).json()["iss_position"]
        return float(data["latitude"]), float(data["longitude"])
    except Exception:
        return None

def geocode(place):
    """Returns (lat, lon) for a city name, or None if not found."""
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": "iss-sighting-app"},
            timeout=8,
        ).json()
        return float(res[0]["lat"]), float(res[0]["lon"])
    except Exception:
        return None

@app.route("/")
def index():
    sightings = Sighting.query.order_by(Sighting.id.desc()).all()
    return render_template("index.html", sightings=sightings, iss=get_iss_position())

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        observer = request.form["observer"].strip()
        place = request.form["place"].strip()
        note = request.form.get("note", "").strip()

        if not observer or not place:
            flash("Please enter your name and a city.", "error")
            return render_template("add.html", form=request.form)

        coords = geocode(place)
        if coords is None:
            flash(f'Could not find "{place}". Try a different spelling.', "error")
            return render_template("add.html", form=request.form)

        iss = get_iss_position()
        if iss is None:
            flash("Could not reach the ISS API. Please try again.", "error")
            return render_template("add.html", form=request.form)

        dist = distance_km(*coords, *iss)
        db.session.add(Sighting(
            observer=observer,
            place=place,
            observer_lat=coords[0],
            observer_lon=coords[1],
            iss_lat=iss[0],
            iss_lon=iss[1],
            distance_km=dist,
            visibility=get_visibility_status(dist),
            note=note,
        ))
        db.session.commit()
        flash("Sighting added.", "success")
        return redirect(url_for("index"))

    return render_template("add.html", form={})

@app.route("/edit/<int:sighting_id>", methods=["GET", "POST"])
def edit(sighting_id):
    sighting = db.get_or_404(Sighting, sighting_id)

    if request.method == "POST":
        observer = request.form["observer"].strip()
        place = request.form["place"].strip()
        note = request.form.get("note", "").strip()

        if not observer or not place:
            flash("Please enter your name and a city.", "error")
            return render_template("edit.html", sighting=sighting, form=request.form)

        # new city -> new coordinates -> new distance
        if place != sighting.place:
            coords = geocode(place)
            if coords is None:
                flash(f'Could not find "{place}". Try a different spelling.', "error")
                return render_template("edit.html", sighting=sighting, form=request.form)
            sighting.observer_lat, sighting.observer_lon = coords
            sighting.distance_km = distance_km(*coords, sighting.iss_lat, sighting.iss_lon)
            sighting.visibility = get_visibility_status(sighting.distance_km)

        sighting.observer = observer
        sighting.place = place
        sighting.note = note
        db.session.commit()
        flash("Changes saved.", "success")
        return redirect(url_for("index"))

    return render_template("edit.html", sighting=sighting, form=sighting)

@app.route("/delete/<int:sighting_id>", methods=["POST"])
def delete(sighting_id):
    db.session.delete(db.get_or_404(Sighting, sighting_id))
    db.session.commit()
    flash("Sighting deleted.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)