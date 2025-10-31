# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import json

# -------------------------- #
# APP CONFIG & HEADER
# -------------------------- #
st.set_page_config(
    page_title="DC Site Scout",
    page_icon="rocket",
    layout="wide"
)

st.title("DC Site Scout")
st.markdown("""
**AI-Powered Data Center Site Selection**  
Upload land → Get AI-ranked sites in 10 seconds  
[Live Demo](https://dc-site-scout.streamlit.app) · [GitHub](https://github.com/Bmaina/dc-site-scout)
""", unsafe_allow_html=True)

# -------------------------- #
# MOCK GEE DATA (DEPLOYABLE)
# -------------------------- #
def sample(geom):
    return {
        "elev_m": 150,
        "flood_pct": 2.1,
        "power_km": 1.8,
        "latency_ms": 12,
        "cost_mw": 65
    }

# -------------------------- #
# MOCK AI RANKING (LOOKS REAL)
# -------------------------- #
def rank_sites(sites):
    st.info("AI Ranking (Mock Mode — Fully Deployable)")
    scores = {
        "Northern Virginia": 95,
        "Phoenix / Mesa": 90,
        "Atlanta": 85,
        "Dallas-Fort Worth": 78,
        "Hillsboro / Portland": 82,
        "Chicago": 60
    }
    return [
        {
            "name": s["name"],
            "score": scores.get(s["name"], 70),
            "justification": f"Mock: {s['name']} — Power: {s.get('power_km', 0):.1f}km, Flood: {s.get('flood_pct', 0):.1f}%"
        }
        for s in sites
    ]

# -------------------------- #
# UI + MAP + MARKERS
# -------------------------- #
uploaded = st.file_uploader("Upload GeoJSON", type=["geojson"])

if uploaded:
    with st.spinner("Processing sites..."):
        st.session_state.sites = []
        bounds = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        geo = json.load(uploaded)
        for f in geo["features"]:
            coords = f["geometry"]["coordinates"][0][0]
            lon, lat = coords[0], coords[1]
            name = f["properties"].get("name", "Site")
            site = {"name": name, "lat": lat, "lon": lon}
            site.update(sample(None))  # Mock GEE
            st.session_state.sites.append(site)
            bounds[0] = min(bounds[0], lon)
            bounds[1] = min(bounds[1], lat)
            bounds[2] = max(bounds[2], lon)
            bounds[3] = max(bounds[3], lat)
        st.session_state.bounds = bounds

@st.cache_resource
def get_map():
    if "bounds" in st.session_state:
        b = st.session_state.bounds
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
        m = folium.Map(location=center, zoom_start=6)
    else:
        m = folium.Map(location=[38, -98], zoom_start=4)
    m.add_child(folium.LatLngPopup())
    Draw(export=False, draw_options={
        "polyline": False, "rectangle": True, "circle": False,
        "marker": True, "circlemarker": False, "polygon": True
    }).add_to(m)
    folium.TileLayer('Stamen Terrain').add_to(m)
    folium.TileLayer('Esri.WorldImagery').add_to(m)
    folium.LayerControl().add_to(m)
    return m

col_map, col_rank = st.columns([3, 1])

with col_map:
    m = get_map()
    out = st_folium(m, height=750, width="100%", key="map")

if st.session_state.get("sites") and not st.session_state.get("ranked"):
    with st.spinner("AI Ranking..."):
        results = rank_sites(st.session_state.sites)
        st.session_state.ranked_results = results
        st.session_state.ranked = True

# Add markers with color
for site in st.session_state.get("sites", []):
    score_obj = next((r for r in st.session_state.get("ranked_results", []) if r["name"] == site["name"]), None)
    score = score_obj["score"] if score_obj else None
    color = "green" if score and score >= 80 else "orange" if score and score >= 60 else "red"
    
    popup = f"""
    <b>{site['name']}</b><br>
    Score: <b>{score or 'N/A'}</b><br>
    Power: {site.get('power_km', 'N/A')} km<br>
    Flood Risk: {site.get('flood_pct', 'N/A')}% 
    """
    folium.Marker(
        location=[site["lat"], site["lon"]],
        popup=folium.Popup(popup, max_width=300),
        tooltip=site["name"],
        icon=folium.Icon(color=color, icon="info-sign")
    ).add_to(m)

# RANKING PANEL
with col_rank:
    st.markdown("### AI Rankings")
    if st.session_state.get("ranked"):
        for r in sorted(st.session_state.ranked_results, key=lambda x: x["score"], reverse=True):
            badge = "Excellent" if r["score"] >= 80 else "Good" if r["score"] >= 60 else "High Risk"
            st.write(f"**{r['name']}** – **{r['score']}** – {r['justification']}")
    else:
        st.info("Upload a GeoJSON file to start")