# streamlit_app.py  -  ISS Sighting Tracker (Streamlit edition, chatpata theme)
# Run from the sqlAlchemy folder:  streamlit run streamlit_app.py
# It uses the SAME database as the Flask version: instance/database.db

from contextlib import contextmanager
from datetime import datetime
from math import asin, atan2, cos, degrees, pi, radians, sin, sqrt
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

st.set_page_config(page_title="ISS Sighting Tracker", page_icon="🛰️", layout="wide")

# =====================================================================
# 1. DATABASE  (SQLAlchemy + SQLite, same table as the Flask project)
# =====================================================================
DB_DIR = Path(__file__).parent / "instance"
DB_DIR.mkdir(exist_ok=True)
engine = create_engine(f"sqlite:///{DB_DIR / 'database.db'}")
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Sighting(Base):
    __tablename__ = "sighting"  # Flask-SQLAlchemy used this exact name
    id = Column(Integer, primary_key=True)
    observer = Column(String(100), nullable=False)
    place = Column(String(100), nullable=False)
    observer_lat = Column(Float, nullable=False)
    observer_lon = Column(Float, nullable=False)
    iss_lat = Column(Float, nullable=False)
    iss_lon = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    visibility = Column(String(100), nullable=False)
    note = Column(String(255), default="")
    # new columns (added automatically to an old database below)
    created_at = Column(DateTime, default=datetime.utcnow)
    altitude_km = Column(Float)


@st.cache_resource
def init_db():
    """Create the table, and add the new columns if the old Flask database lacks them."""
    Base.metadata.create_all(engine)
    existing = {c["name"] for c in inspect(engine).get_columns("sighting")}
    with engine.begin() as conn:
        if "created_at" not in existing:
            conn.execute(text("ALTER TABLE sighting ADD COLUMN created_at DATETIME"))
        if "altitude_km" not in existing:
            conn.execute(text("ALTER TABLE sighting ADD COLUMN altitude_km FLOAT"))
    return True


@contextmanager
def db_session():
    s = Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def load_sightings():
    with db_session() as s:
        rows = s.query(Sighting).order_by(Sighting.id.desc()).all()
        cols = [c.name for c in Sighting.__table__.columns]
        return pd.DataFrame([{c: getattr(r, c) for c in cols} for r in rows], columns=cols)


# =====================================================================
# 2. EXTERNAL APIs + MATHS
# =====================================================================
@st.cache_data(ttl=3)
def get_iss():
    """Live ISS position. Returns a dict, or None if both APIs fail."""
    try:
        d = requests.get("https://api.wheretheiss.at/v1/satellites/25544", timeout=8).json()
        return {"lat": d["latitude"], "lon": d["longitude"], "alt": d["altitude"],
                "vel": d["velocity"], "daylight": d["visibility"]}
    except Exception:
        pass
    try:
        d = requests.get("http://api.open-notify.org/iss-now.json", timeout=8).json()["iss_position"]
        return {"lat": float(d["latitude"]), "lon": float(d["longitude"]),
                "alt": None, "vel": None, "daylight": None}
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(place):
    """City name -> (lat, lon, full name), or None."""
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": place, "format": "json", "limit": 1},
                         headers={"User-Agent": "iss-sighting-app"}, timeout=8).json()
        return float(r[0]["lat"]), float(r[0]["lon"]), r[0]["display_name"]
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_crew():
    """People currently on the ISS."""
    try:
        data = requests.get("http://api.open-notify.org/astros.json", timeout=8).json()
        return [p["name"] for p in data["people"] if p["craft"] == "ISS"]
    except Exception:
        return []


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * 6371 * asin(sqrt(a)), 1)


def visibility_status(dist):
    if dist <= 1500:
        return "Clearly visible"
    if dist <= 3000:
        return "Partly visible"
    return "Not visible"


def visibility_pct(dist):
    """0-100 score: 100 = ISS directly overhead, 0 = 3000 km or more away."""
    return max(0, min(100, round(100 * (1 - dist / 3000))))


def footprint(lat, lon, radius_km=2200, n=90):
    """Circle on the map showing roughly where the ISS can be seen from."""
    d, la1, lo1 = radius_km / 6371, radians(lat), radians(lon)
    lats, lons, prev = [], [], None
    for i in range(n + 1):
        b = 2 * pi * i / n
        la2 = asin(sin(la1) * cos(d) + cos(la1) * sin(d) * cos(b))
        lo2 = lo1 + atan2(sin(b) * sin(d) * cos(la1), cos(d) - sin(la1) * sin(la2))
        lo = (degrees(lo2) + 540) % 360 - 180
        if prev is not None and abs(lo - prev) > 180:  # break the line at the date line
            lats.append(None)
            lons.append(None)
        lats.append(degrees(la2))
        lons.append(lo)
        prev = lo
    return lats, lons


# =====================================================================
# 3. LOOK AND FEEL  (chatpata theme - custom CSS)
# =====================================================================
COLORS = {"Clearly visible": "#7dff6b", "Partly visible": "#ffd23f", "Not visible": "#ff5a5f"}
BADGE = {"Clearly visible": "green", "Partly visible": "yellow", "Not visible": "red"}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');
:root { --bg:#150a2e; --bg2:#2a0f4f; --panel:#24104a; --panel2:#36186b; --line:#5b34a3;
        --text:#ffffff; --muted:#cdbff0; --pink:#ff3d8b; --orange:#ff8a00; --yellow:#ffd23f;
        --cyan:#22e0f2; --lime:#7dff6b; --red:#ff5a5f; --accent:#ff3d8b; }

html, body, [class*="css"], .stApp { font-family:'Inter',sans-serif; color:var(--text); }
.stApp {
    background:
      radial-gradient(700px 400px at 90% -5%, rgba(255,61,139,.35), transparent 70%),
      radial-gradient(600px 400px at -5% 20%, rgba(34,224,242,.22), transparent 70%),
      linear-gradient(160deg, var(--bg) 0%, var(--bg2) 100%);
    background-attachment: fixed;
}
#MainMenu, footer { visibility:hidden; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:2rem; max-width:1280px; }
h1,h2,h3,h4 { font-family:'Poppins',sans-serif !important; letter-spacing:-0.01em; color:var(--text); }
h3 { color:var(--yellow) !important; }
p, span, li, label, .stMarkdown, [data-testid="stCaptionContainer"] { color:var(--text); }
[data-testid="stCaptionContainer"], .muted { color:var(--muted) !important; }
.muted { font-size:.92rem; }

/* widget labels + inputs: always readable */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { color:var(--yellow) !important; font-weight:600; }
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
    background:var(--bg) !important; color:var(--text) !important;
    border:2px solid var(--line) !important; border-radius:10px !important; }
.stTextInput input::placeholder { color:#8f7cc0 !important; }
.stTextInput input:focus { border-color:var(--cyan) !important; box-shadow:0 0 0 3px rgba(34,224,242,.25) !important; }
div[data-baseweb="select"] span, div[data-baseweb="select"] svg { color:var(--text) !important; fill:var(--text) !important; }
div[data-baseweb="popover"] ul { background:var(--panel) !important; }
div[data-baseweb="popover"] li { color:var(--text) !important; }
[data-testid="stSidebar"] { background:var(--panel); border-right:3px solid var(--pink); }
[data-testid="stSidebar"] * { color:var(--text); }
[data-testid="stAlert"] { border-radius:12px; border:2px solid var(--line); }

/* hero */
.hero h1 { font-size:2.7rem; margin:0; font-weight:800; }
.hero h1::before { content:"🛰️ "; }
.hero h1 span { background:linear-gradient(90deg,var(--yellow),var(--pink)); -webkit-background-clip:text;
                background-clip:text; color:transparent; }
.hero p { color:var(--muted); margin:4px 0 22px; font-size:1.05rem; }

/* cards */
.kpi, .result, .crew, [data-testid="stForm"], [data-testid="stMetric"] {
    background:var(--panel); border:2px solid var(--line); border-radius:14px;
    box-shadow:5px 5px 0 rgba(0,0,0,.35); }
.kpi { padding:16px 18px; height:100%; }
.kpi .v { font-family:'Poppins',sans-serif; font-size:1.75rem; font-weight:800; font-variant-numeric:tabular-nums; color:var(--yellow); }
.kpi .l { color:var(--muted); font-size:.9rem; }
.kpi.live { border-color:var(--cyan); box-shadow:5px 5px 0 rgba(34,224,242,.35); }
.kpi.live .v { color:var(--cyan); }

.dot { display:inline-block; width:10px; height:10px; border-radius:50%; background:var(--lime);
       margin-right:8px; animation:pulse 2s infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(125,255,107,.7)} 70%{box-shadow:0 0 0 12px rgba(125,255,107,0)} 100%{box-shadow:0 0 0 0 rgba(125,255,107,0)} }
@media (prefers-reduced-motion: reduce) { .dot { animation:none; } }

.badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.82rem; font-weight:700; color:#1a0836; }
.badge.green  { background:var(--lime); }
.badge.yellow { background:var(--yellow); }
.badge.red    { background:var(--red); color:#fff; }

.result { padding:20px; margin-top:14px; }
.result h3 { margin:0 0 6px; }
.bar { height:10px; background:var(--bg); border-radius:99px; overflow:hidden; margin:10px 0 4px; }
.bar > div { height:100%; border-radius:99px; }
.crew { padding:12px 16px; margin-bottom:12px; font-weight:600; }
[data-testid="stForm"] { padding:22px; }
[data-testid="stMetric"] { padding:14px 16px; }
[data-testid="stMetricLabel"] p { color:var(--muted) !important; }
[data-testid="stMetricValue"] { color:var(--pink) !important; font-family:'Poppins',sans-serif; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap:8px; border-bottom:2px solid var(--line); }
.stTabs [data-baseweb="tab"] { height:44px; padding:0 18px; border-radius:999px 999px 0 0; color:var(--muted); font-weight:600; }
.stTabs [data-baseweb="tab"]:hover { color:var(--text); }
.stTabs [aria-selected="true"] { color:#1a0836 !important; background:var(--yellow); }
.stTabs [data-baseweb="tab-highlight"] { background:var(--pink); height:3px; }

/* buttons */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius:999px; font-weight:700; height:44px; padding:0 22px;
    color:var(--text); background:transparent; border:2px solid var(--cyan);
    box-shadow:3px 3px 0 rgba(34,224,242,.4); transition:transform .12s, box-shadow .12s; }
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
    transform:translate(-1px,-2px); box-shadow:5px 5px 0 rgba(34,224,242,.5); color:var(--text); border-color:var(--cyan); }
.stFormSubmitButton > button[kind="primary"], .stButton > button[kind="primary"] {
    background:linear-gradient(135deg,var(--pink),var(--orange)); color:#fff; border:2px solid #fff; box-shadow:3px 3px 0 #000; }
.stFormSubmitButton > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {
    box-shadow:5px 5px 0 #000; color:#fff; border-color:#fff; }
.stButton > button:disabled { opacity:.45; box-shadow:none; }

/* table */
[data-testid="stDataFrame"] { border:2px solid var(--line); border-radius:14px; overflow:hidden; }
hr { border-color:var(--line) !important; }
</style>
""", unsafe_allow_html=True)


def kpi(label, value, extra_class=""):
    return f'<div class="kpi {extra_class}"><div class="v">{value}</div><div class="l">{label}</div></div>'


def badge(status):
    return f'<span class="badge {BADGE[status]}">{status}</span>'


def style_fig(fig, height=330):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#ffffff", family="Inter"),
                      title_font=dict(family="Poppins", size=16, color="#ffd23f"),
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#3d2273", zeroline=False)
    fig.update_yaxes(gridcolor="#3d2273", zeroline=False)
    return fig


# =====================================================================
# 4. SIDEBAR  (settings)
# =====================================================================
init_db()

with st.sidebar:
    st.markdown("### Settings")
    unit = st.radio("Distance units", ["km", "mi"], horizontal=True)
    auto = st.toggle("Live updates (every 10 s)", value=True)
    default_name = st.text_input("Default observer name", value="")
    st.divider()
    st.caption("Visibility guide")
    st.markdown(badge("Clearly visible") + " within 1,500 km", unsafe_allow_html=True)
    st.markdown(badge("Partly visible") + " within 3,000 km", unsafe_allow_html=True)
    st.markdown(badge("Not visible") + " further away", unsafe_allow_html=True)


def dist(km):
    """Format a distance in the chosen unit."""
    return f"{km * 0.621371:,.0f} mi" if unit == "mi" else f"{km:,.0f} km"


# =====================================================================
# 5. DASHBOARD PIECES
# =====================================================================
def build_map(iss, trail, df):
    fig = go.Figure()
    # footprint of where the ISS is visible from right now
    flat, flon = footprint(iss["lat"], iss["lon"])
    fig.add_trace(go.Scattergeo(lat=flat, lon=flon, mode="lines", name="Visibility range",
                                line=dict(color="rgba(34,224,242,.9)", width=2, dash="dot"), hoverinfo="skip"))
    # past sightings: line from the observer to where the ISS was at that moment
    for _, r in df.head(15).iterrows():
        fig.add_trace(go.Scattergeo(lat=[r.observer_lat, r.iss_lat], lon=[r.observer_lon, r.iss_lon],
                                    mode="lines", showlegend=False, hoverinfo="skip",
                                    line=dict(color=COLORS[r.visibility], width=1.5), opacity=0.6))
    if not df.empty:
        fig.add_trace(go.Scattergeo(
            lat=df.observer_lat, lon=df.observer_lon, mode="markers", name="Observers",
            marker=dict(size=10, color=[COLORS[v] for v in df.visibility], line=dict(color="#150a2e", width=1.5)),
            text=df.observer + " · " + df.place + "<br>" + df.visibility, hoverinfo="text"))
    # trail of the live ISS
    if len(trail) > 1:
        fig.add_trace(go.Scattergeo(lat=[p[0] for p in trail], lon=[p[1] for p in trail], mode="lines",
                                    name="ISS trail", line=dict(color="#ffd23f", width=3), hoverinfo="skip"))
    fig.add_trace(go.Scattergeo(lat=[iss["lat"]], lon=[iss["lon"]], mode="markers+text", name="ISS now",
                                text=["ISS"], textposition="top center", textfont=dict(color="#ffffff", size=14),
                                marker=dict(size=18, color="#ff3d8b", symbol="circle",
                                            line=dict(color="white", width=2.5)),
                                hovertemplate="ISS<br>%{lat:.2f}, %{lon:.2f}<extra></extra>"))
    fig.update_geos(projection_type="natural earth", showland=True, landcolor="#3b2278",
                    showocean=True, oceancolor="#150a2e", showcountries=True, countrycolor="#8a66d9",
                    coastlinecolor="#ff3d8b", showframe=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=470, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#ffffff"), legend=dict(orientation="h", y=0.02, x=0.01,
                                                              bgcolor="rgba(21,10,46,.75)"))
    return fig


def live_panel():
    """Everything that refreshes by itself: live ISS numbers + the map."""
    iss = get_iss()
    if iss is None:
        st.error("Could not reach the ISS API. Check your internet connection and refresh.")
        return
    trail = st.session_state.setdefault("trail", [])
    if not trail or trail[-1] != (iss["lat"], iss["lon"]):
        trail.append((iss["lat"], iss["lon"]))
        del trail[:-60]  # keep the last 60 points

    c = st.columns(4)
    c[0].markdown(kpi('<span class="dot"></span>Latitude', f"{iss['lat']:.3f}°", "live"), unsafe_allow_html=True)
    c[1].markdown(kpi("Longitude", f"{iss['lon']:.3f}°", "live"), unsafe_allow_html=True)
    c[2].markdown(kpi("Altitude", dist(iss["alt"]) if iss["alt"] else "n/a", "live"), unsafe_allow_html=True)
    speed = f"{iss['vel'] * (0.621371 if unit == 'mi' else 1):,.0f} {unit}/h" if iss["vel"] else "n/a"
    c[3].markdown(kpi("Speed", speed, "live"), unsafe_allow_html=True)
    st.plotly_chart(build_map(iss, trail, load_sightings()), use_container_width=True,
                    config={"displayModeBar": False})


def save_new(observer, place, note):
    """Geocode, read the ISS, calculate and save. Returns (ok, message)."""
    geo = geocode(place)
    if geo is None:
        return False, f'Could not find "{place}". Try a different spelling.'
    iss = get_iss()
    if iss is None:
        return False, "Could not reach the ISS API. Please try again."
    d = haversine(geo[0], geo[1], iss["lat"], iss["lon"])
    with db_session() as s:
        row = Sighting(observer=observer, place=place, observer_lat=geo[0], observer_lon=geo[1],
                       iss_lat=iss["lat"], iss_lon=iss["lon"], distance_km=d,
                       visibility=visibility_status(d), note=note,
                       created_at=datetime.utcnow(), altitude_km=iss["alt"])
        s.add(row)
        s.flush()
        st.session_state["last"] = {"observer": observer, "place": geo[2], "dist": d,
                                    "status": row.visibility, "iss": (iss["lat"], iss["lon"])}
    return True, "Sighting added."


# =====================================================================
# 6. PAGE
# =====================================================================
st.markdown('<div class="hero"><h1>ISS <span>Sighting Tracker</span></h1>'
            '<p>Follow the International Space Station live and log whether you can see it from your city.</p></div>',
            unsafe_allow_html=True)

tab_dash, tab_add, tab_manage, tab_stats, tab_crew = st.tabs(
    ["Live dashboard", "Add sighting", "Manage sightings", "Analytics", "Crew on board"])

# ---------- TAB 1: dashboard ----------
with tab_dash:
    st.fragment(run_every=10 if auto else None)(live_panel)()
    df = load_sightings()
    st.markdown("#### Your log at a glance")
    k = st.columns(4)
    k[0].markdown(kpi("Sightings logged", len(df)), unsafe_allow_html=True)
    k[1].markdown(kpi("Clearly visible", int((df.visibility == "Clearly visible").sum()) if len(df) else 0),
                  unsafe_allow_html=True)
    k[2].markdown(kpi("Average distance", dist(df.distance_km.mean()) if len(df) else "n/a"), unsafe_allow_html=True)
    k[3].markdown(kpi("Closest ever", dist(df.distance_km.min()) if len(df) else "n/a"), unsafe_allow_html=True)

# ---------- TAB 2: add ----------
with tab_add:
    st.markdown("### Add a sighting")
    st.caption("Enter your city. We find its coordinates and compare them with where the ISS is right now.")
    with st.form("add_form", clear_on_submit=True):
        a, b = st.columns(2)
        observer = a.text_input("Your name", value=default_name, placeholder="e.g. Rajnish")
        place = b.text_input("City", placeholder="e.g. Chennai")
        note = st.text_input("Note (optional)", placeholder="e.g. Saw it just after sunset")
        go_add = st.form_submit_button("Add sighting", type="primary")
    if go_add:
        if not observer.strip() or not place.strip():
            st.error("Please enter your name and a city.")
        else:
            with st.spinner("Finding your city and the ISS..."):
                ok, msg = save_new(observer.strip(), place.strip(), note.strip())
            (st.success if ok else st.error)(msg)
            if ok:
                st.toast("Sighting added", icon="🛰️")
    last = st.session_state.get("last")
    if last:
        pct = visibility_pct(last["dist"])
        st.markdown(
            f'<div class="result"><h3>{last["observer"]}, here is your result</h3>'
            f'<div class="muted">{last["place"]}</div>'
            f'{badge(last["status"])} &nbsp; The ISS is <b>{dist(last["dist"])}</b> from you '
            f'(over {last["iss"][0]:.2f}°, {last["iss"][1]:.2f}°).'
            f'<div class="bar"><div style="width:{pct}%;background:{COLORS[last["status"]]}"></div></div>'
            f'<span style="color:var(--muted);font-size:.85rem">Visibility score {pct} / 100</span></div>',
            unsafe_allow_html=True)

# ---------- TAB 3: manage ----------
with tab_manage:
    df = load_sightings()
    st.markdown("### All sightings")
    if df.empty:
        st.info("No sightings yet. Open the Add sighting tab to log your first one.")
    else:
        f1, f2, f3 = st.columns([2, 2, 1])
        q = f1.text_input("Search", placeholder="Name, city or note", label_visibility="collapsed")
        vis_filter = f2.multiselect("Visibility", list(COLORS), default=list(COLORS), label_visibility="collapsed")
        order = f3.selectbox("Sort", ["Newest", "Closest"], label_visibility="collapsed")

        view = df[df.visibility.isin(vis_filter)]
        if q:
            mask = view[["observer", "place", "note"]].fillna("").apply(
                lambda col: col.str.contains(q, case=False)).any(axis=1)
            view = view[mask]
        view = view.sort_values("distance_km") if order == "Closest" else view

        show = pd.DataFrame({
            "ID": view.id, "Observer": view.observer, "City": view.place,
            f"Distance ({unit})": view.distance_km * (0.621371 if unit == "mi" else 1),
            "Visibility": view.visibility, "Note": view.note,
            "Logged": pd.to_datetime(view.created_at).dt.strftime("%d %b %Y, %H:%M"),
        })
        st.dataframe(show, hide_index=True, use_container_width=True,
                     column_config={f"Distance ({unit})": st.column_config.NumberColumn(format="%.0f")})
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "sightings.csv", "text/csv")

        st.divider()
        st.markdown("### Edit or delete")
        labels = {int(r.id): f"#{r.id}  {r.observer} · {r.place}" for r in df.itertuples()}
        chosen = st.selectbox("Pick a sighting", list(labels), format_func=labels.get)
        row = df[df.id == chosen].iloc[0]

        e1, e2 = st.columns([3, 2])
        with e1.form(f"edit_{chosen}"):
            n1, n2 = st.columns(2)
            new_obs = n1.text_input("Your name", value=row.observer)
            new_place = n2.text_input("City", value=row.place)
            new_note = st.text_input("Note", value=row.note or "")
            remeasure = st.checkbox("Measure again against the ISS right now")
            save = st.form_submit_button("Save changes", type="primary")
        if save:
            if not new_obs.strip() or not new_place.strip():
                st.error("Please enter your name and a city.")
            else:
                geo, iss, error = None, None, None
                if new_place.strip() != row.place:
                    geo = geocode(new_place.strip())
                    error = None if geo else f'Could not find "{new_place}". Try a different spelling.'
                if remeasure and not error:
                    iss = get_iss()
                    error = None if iss else "Could not reach the ISS API."
                if error:
                    st.error(error)
                else:
                    with db_session() as s:
                        rec = s.get(Sighting, int(chosen))
                        rec.observer, rec.place, rec.note = new_obs.strip(), new_place.strip(), new_note.strip()
                        if geo:
                            rec.observer_lat, rec.observer_lon = geo[0], geo[1]
                        if iss:
                            rec.iss_lat, rec.iss_lon, rec.altitude_km = iss["lat"], iss["lon"], iss["alt"]
                        if geo or iss:  # position changed -> recalculate
                            rec.distance_km = haversine(rec.observer_lat, rec.observer_lon, rec.iss_lat, rec.iss_lon)
                            rec.visibility = visibility_status(rec.distance_km)
                    st.toast("Changes saved", icon="✅")
                    st.rerun()

        with e2:
            st.markdown('<div class="result" style="margin-top:0;border-color:#ff5a5f"><h3>Delete this sighting</h3>'
                        '<div class="muted">This cannot be undone.</div></div>', unsafe_allow_html=True)
            sure = st.checkbox("Yes, delete it", key=f"sure_{chosen}")
            if st.button("Delete sighting", disabled=not sure):
                with db_session() as s:
                    s.delete(s.get(Sighting, int(chosen)))
                st.toast("Sighting deleted", icon="🗑️")
                st.rerun()

# ---------- TAB 4: analytics ----------
with tab_stats:
    df = load_sightings()
    st.markdown("### Analytics")
    if len(df) < 2:
        st.info("Log at least two sightings to unlock charts.")
    else:
        c1, c2 = st.columns(2)
        counts = df.visibility.value_counts().reset_index()
        counts.columns = ["Visibility", "Count"]
        fig = px.pie(counts, names="Visibility", values="Count", hole=0.6, color="Visibility",
                     color_discrete_map=COLORS, title="How often you could see it")
        fig.update_traces(marker=dict(line=dict(color="#150a2e", width=2)))
        c1.plotly_chart(style_fig(fig), use_container_width=True, config={"displayModeBar": False})

        by_city = df.groupby("place").distance_km.mean().sort_values().reset_index()
        fig = px.bar(by_city, x="distance_km", y="place", orientation="h", title="Average distance by city",
                     labels={"distance_km": "km", "place": ""})
        fig.update_traces(marker_color="#22e0f2")
        c2.plotly_chart(style_fig(fig), use_container_width=True, config={"displayModeBar": False})

        d = df.dropna(subset=["created_at"]).sort_values("created_at")
        if len(d) >= 2:
            fig = px.scatter(d, x="created_at", y="distance_km", color="visibility", color_discrete_map=COLORS,
                             title="Distance over time", labels={"created_at": "", "distance_km": "km"})
            fig.update_traces(marker=dict(size=12, line=dict(color="#150a2e", width=1)))
            st.plotly_chart(style_fig(fig, 340), use_container_width=True, config={"displayModeBar": False})

        top = df.observer.value_counts().head(8).reset_index()
        top.columns = ["Observer", "Sightings"]
        fig = px.bar(top, x="Observer", y="Sightings", title="Most active observers")
        fig.update_traces(marker_color="#ff3d8b")
        st.plotly_chart(style_fig(fig, 300), use_container_width=True, config={"displayModeBar": False})

# ---------- TAB 5: crew ----------
with tab_crew:
    st.markdown("### Who is on the ISS right now")
    crew = get_crew()
    if not crew:
        st.info("Crew list is not available at the moment.")
    else:
        cols = st.columns(3)
        for i, name in enumerate(crew):
            cols[i % 3].markdown(f'<div class="crew">👨‍🚀 <b>{name}</b></div>', unsafe_allow_html=True)
    st.markdown("#### Quick facts")
    f = st.columns(3)
    f[0].metric("Orbit time", "about 92 min")
    f[1].metric("Sunrises per day", "about 16")
    f[2].metric("Orbit inclination", "51.6°")