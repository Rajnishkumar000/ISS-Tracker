<!-- # ISS Sighting Tracker

A small Flask web app where you log whether the International Space Station (ISS) is near your city.

Enter your name and a city. The app finds the city's coordinates, gets the ISS's current position, calculates the distance between them, and saves the result as a **sighting**.

## Features

- **Add** a sighting (name, city, optional note)
- **View** all sightings in a table, with stats (total, clearly visible, closest distance)
- **Edit** a sighting (changing the city recalculates the distance)
- **Delete** a sighting
- Shows the **live ISS position** on the home page

## Tech used

| Part | Tool |
|---|---|
| Backend | Python, Flask |
| Database | SQLite, through Flask-SQLAlchemy |
| Frontend | HTML (Jinja2 templates) and CSS |
| ISS location | [Open Notify API](http://api.open-notify.org/iss-now.json) |
| City to coordinates | [Nominatim (OpenStreetMap)](https://nominatim.openstreetmap.org/) |

## Project structure

```
project-folder/
├── app.py                 # Flask app: model, helpers, routes
├── templates/
│   ├── index.html         # list of sightings
│   ├── add.html           # add form
│   └── edit.html          # edit form
├── static/
│   └── css/
│       └── style.css      # styling
└── instance/
    └── database.db        # SQLite database (created automatically)
```

## How it works (MVC)

- **Model**: the `Sighting` class in `app.py` describes the database table.
- **View**: the HTML files in `templates/` are what the user sees.
- **Controller**: the route functions in `app.py` receive requests, use the model, and pick the view.

### Routes

| URL | Method | What it does |
|---|---|---|
| `/` | GET | Show all sightings and the live ISS position |
| `/add` | GET | Show the empty add form |
| `/add` | POST | Save a new sighting |
| `/edit/<id>` | GET | Show the edit form |
| `/edit/<id>` | POST | Save changes |
| `/delete/<id>` | POST | Delete the sighting |

### What happens when you add a sighting

1. You submit your name and city.
2. `geocode()` turns the city into latitude and longitude.
3. `get_iss_position()` gets the ISS's current latitude and longitude.
4. `distance_km()` calculates the distance between the two using the haversine formula.
5. `get_visibility_status()` turns the distance into a label.
6. The sighting is saved to the database, and you are sent back to the home page.

### Visibility rules

| Distance | Result |
|---|---|
| 800 km or less | Clearly visible |
| 801 to 2000 km | Partly visible |
| More than 2000 km | Not visible |

These thresholds are a simple rule of thumb. Real visibility also depends on night time and sunlight.

## Setup

### 1. Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install flask flask-sqlalchemy requests
```

On macOS or Linux, activate with `source .venv/bin/activate` instead.

### 2. Run the app

```powershell
python app.py
```

### 3. Open in the browser

Go to [http://127.0.0.1:5000](http://127.0.0.1:5000)

The database file is created automatically the first time you run the app.

## Notes and limitations

- An internet connection is required (the app calls two outside APIs).
- If the city isn't found or the ISS API is down, the form simply reloads.
- `db.create_all()` only creates missing tables. If you change the `Sighting` model later, delete `instance/database.db` so it is rebuilt.
- `debug=True` is for development only.
- The Nominatim API has a usage limit of about one request per second, which is fine for a small project.

## Possible improvements

- Show error and success messages to the user
- Check whether it is night at the user's location
- Show the ISS and the observer on a map
- Add search and filtering for sightings -->


# 🛰️ ISS Sighting Tracker

Track the International Space Station in real time and log whether you could see it from your city.

Enter your name and a city. The app finds the city's coordinates, reads the ISS's live position, calculates the distance between the two, and saves the result with a visibility rating.

The project has **two front-ends on one database**:

- **Streamlit app** (`streamlit_app.py`): live dashboard, map, analytics, CSV export
- **Flask app** (`app.py`): classic server-rendered CRUD app with a Leaflet map

Both read and write the same SQLite file, `instance/database.db`.

---

## 📸 Screenshots (Streamlit app)

### Live dashboard
Live ISS latitude, longitude, altitude and speed, refreshed every 10 seconds, with the world map below.

![Live dashboard](docs/screenshots/dashboard.png)

### Live map and log summary
The ISS, its trail, the dotted visibility circle, and lines from each observer to where the ISS was when they logged a sighting.

![Live map and log summary](docs/screenshots/live-map.png)

### Add a sighting
![Add sighting](docs/screenshots/add-sighting.png)

### Manage sightings
Search, filter by visibility, sort, download CSV, then edit or delete.

![Manage sightings](docs/screenshots/manage-sightings.png)

### Analytics
![Analytics](docs/screenshots/analytics.png)

---

## ✨ Features

- **Live ISS data**: position, altitude and speed, auto-refreshing every 10 seconds
- **City lookup**: type a city name and it is geocoded automatically (OpenStreetMap Nominatim)
- **Distance and visibility**: great-circle (Haversine) distance with a three-level rating
- **Visibility score**: 0 to 100 bar for each new sighting
- **Full CRUD**: add, view, edit and delete sightings
- **Re-measure**: recompute a saved sighting against the ISS's current position
- **Analytics**: visibility breakdown, average distance by city, distance over time, most active observers
- **Search, filter, sort and CSV export**
- **Crew list**: who is on the ISS right now
- **km / mi toggle** and a default observer name in the sidebar
- **API fallback**: if the primary ISS API fails, a second one is used
- **Automatic DB upgrade**: an older Flask database gets the new columns added on first run of the Streamlit app

## 🎯 How visibility is decided

| Distance from ISS | Rating |
|---|---|
| up to 1,500 km | 🟢 Clearly visible |
| up to 3,000 km | 🟡 Partly visible |
| more than 3,000 km | 🔴 Not visible |

> This is a distance-based estimate. It does not account for daylight, cloud cover or the ISS's actual pass times over your location.

---

## 🗂️ Project structure

```
iss-sighting-tracker/
├── streamlit_app.py        # Streamlit app
├── app.py                  # Flask app
├── requirements.txt
├── templates/              # Flask templates
│   ├── index.html
│   ├── add.html
│   └── edit.html
├── static/
│   └── css/style.css       # Flask styles
├── instance/
│   └── database.db         # SQLite database (created automatically)
└── docs/
    └── screenshots/        # Images used in this README
```

## 🚀 Getting started

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd iss-sighting-tracker

# 2. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

### Run the Streamlit app

```bash
streamlit run streamlit_app.py
```

Opens at http://localhost:8501. Needs **Streamlit 1.37+** (the live panel uses `st.fragment(run_every=...)`).

### Run the Flask app

```bash
python app.py
```

Opens at http://127.0.0.1:5000. Needs **Flask-SQLAlchemy 3.0+** (the code uses `db.get_or_404`).

You need an internet connection for both (live ISS data and city lookup).

---

## ⚙️ How it works

1. **Geocode**: the city name goes to OpenStreetMap Nominatim, which returns latitude and longitude.
2. **Read the ISS**: `wheretheiss.at` returns live position, altitude and speed. Open Notify is the fallback.
3. **Calculate**: the Haversine formula gives the distance in km.
4. **Rate**: the distance is mapped to Clearly, Partly or Not visible.
5. **Save**: the record is stored in `instance/database.db` through SQLAlchemy.

The dotted circle on the Streamlit map is a 2,200 km footprint around the ISS, a rough guide to where it can be seen from.

## 🖥️ Streamlit app tabs

| Tab | What it does |
|---|---|
| Live dashboard | ISS numbers, world map with trail and visibility circle, log summary cards |
| Add sighting | Name, city and optional note; instant result with a score bar |
| Manage sightings | Table with search, filter, sort, CSV download; edit, re-measure or delete |
| Analytics | Visibility donut, average distance by city, distance over time, top observers |
| Crew on board | People currently on the ISS and quick orbit facts |

## 🌐 Flask app routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Sightings list, live ISS position, Leaflet map, stats |
| `/add` | GET, POST | Add a new sighting |
| `/edit/<id>` | GET, POST | Edit a sighting (distance recalculated if the city changes) |
| `/delete/<id>` | POST | Delete a sighting |

---

## 🗄️ Database

Single table, `sighting`:

| Column | Type | Notes |
|---|---|---|
| id | Integer | Primary key |
| observer | String(100) | Name of the person |
| place | String(100) | City as typed |
| observer_lat / observer_lon | Float | Geocoded coordinates |
| iss_lat / iss_lon | Float | ISS position at that moment |
| distance_km | Float | Haversine distance |
| visibility | String(100) | Rating |
| note | String(255) | Optional |
| created_at | DateTime | Added by the Streamlit app |
| altitude_km | Float | Added by the Streamlit app |

## 🔌 APIs used

| Purpose | API |
|---|---|
| ISS position, altitude, speed | [wheretheiss.at](https://wheretheiss.at/w/developer) (primary) |
| ISS position fallback and crew | [Open Notify](http://open-notify.org/) |
| City to coordinates | [OpenStreetMap Nominatim](https://nominatim.org/) |

All are free and need no API key. Please follow Nominatim's usage policy (light use, a meaningful User-Agent).

## 🛠️ Tech stack

Python · Streamlit · Flask · SQLAlchemy · SQLite · Plotly · Pandas · Leaflet · Requests

## 🧯 Troubleshooting

| Problem | Fix |
|---|---|
| "Could not reach the ISS API" | Check your internet connection and refresh |
| `Could not find "<city>"` | Try another spelling or add the country, e.g. `Patna, India` |
| `st.fragment` error | `pip install -U streamlit` |
| Charts say "Log at least two sightings" | Add more sightings; charts unlock at two |

## 🔒 Before deploying the Flask app

- Replace `app.secret_key = "secret"` with a long random value from an environment variable.
- Turn off `debug=True` in `app.run(...)`.

## 🔭 Possible improvements

- Predict real ISS passes for a city (visible pass times and direction)
- Factor in daylight and twilight at the observer's location
- User accounts so each person sees only their own log
- Deploy to Streamlit Community Cloud or Render

## 👤 Author

**Rajnish Kumar**