
# app.py
import streamlit as st
import os
import json
ee = geemap.ee
import geemap.foliumap as geemap
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from streamlit_folium import st_folium
from folium.plugins import Draw
import re


# APP HEADER (LIVE VERSION)
# -------------------------- #

st.set_page_config(
    page_title="DC Site Scout",
    page_icon="rocket",   # ← ADDS ROCKET ICON TO BROWSER TAB
    layout="wide"
)


st.set_page_config(page_title="DC Site Scout", layout="wide")
st.title("DC Site Scout")
st.markdown("""
**AI-Powered Data Center Site Selection**  
Upload land → Get AI-ranked sites in 10 seconds  
[Live Demo](https://dc-site-scout.streamlit.app) · [GitHub](https://github.com/yourname/dc-site-scout)
""", unsafe_allow_html=True)


# -------------------------- #
# EARTH ENGINE
# -------------------------- #
@st.cache_resource
def init_ee():
    try:
        ee.Initialize()
        st.success("Earth Engine ready")
        return True
    except Exception as e:
        st.error("GEE not available on Streamlit Cloud")
        st.info("Local testing only")
        return False
    
# -------------------------- #
# ANTHROPIC LLM (GUARANTEED WORKING MODEL)
# -------------------------- #
API_KEY = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
if not API_KEY:
    st.error("Add `ANTHROPIC_API_KEY` in Streamlit Secrets")
    st.stop()

try:
    llm = ChatAnthropic(model="claude-3-haiku-20240307", api_key=API_KEY, temperature=0.3)
    st.success("LLM Connected: claude-3-haiku-20240307")
except Exception as e:
    st.error(f"LLM Failed: {e}")
    llm = None

# -------------------------- #
# PROMPT: FORCE JSON
# -------------------------- #
prompt_batch = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "You are a data-center site expert. "
        "Respond ONLY with valid JSON array. No text outside."
    ),
    HumanMessagePromptTemplate.from_template(
        "Rank these sites (power, flood, latency, cost):\n"
        "{sites}\n\n"
        "Return ONLY:\n"
        "[{{'name': 'Site', 'score': 0-100, 'justification': '1 sentence'}}]"
    )
])

# -------------------------- #
# GEE SAMPLE
# -------------------------- #
def sample(geom):
    data = {}
    try:
        elev = ee.Image("USGS/SRTMGL1_003").reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()
        data["elev_m"] = round(elev.get("elevation", 0), 1)

        flood = ee.Image("USGS/NLCD_RELEASES/2021_REL/NLCD/2021").select('landcover').eq(11)
        data["flood_pct"] = round(flood.reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('landcover', 0) * 100, 1)

        nearest = ee.FeatureCollection("WRI/GPPD/power_plants").distance(geom.centroid()).reduceRegion(ee.Reducer.min(), geom, 1000).getInfo()
        data["power_km"] = round(nearest.get('min', float('inf')) / 1000, 1)

        ashburn = ee.Geometry.Point(-77.5, 39.0)
        data["latency_ms"] = round(geom.centroid().distance(ashburn).getInfo() / 3000, 1)

        urban = ee.Image("USGS/NLCD_RELEASES/2021_REL/NLDLCD/2021").select('landcover').eq(21)
        data["cost_mw"] = round(50 + urban.reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('landcover', 0) * 100, 1)
    except Exception as e:
        data["error"] = str(e)
    return data

# -------------------------- #
# CLEAN DATA
# -------------------------- #
def clean(site):
    return {
        "name": site["name"],
        "elev": site.get("elev_m"),
        "flood": site.get("flood_pct"),
        "power": site.get("power_km"),
        "latency": site.get("latency_ms"),
        "cost": site.get("cost_mw")
    }

# -------------------------- #
# SAFE JSON EXTRACT
# -------------------------- #
def extract_json(text):
    text = text.strip()
    start = text.find('[')
    end = text.rfind(']') + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except:
        return None

# -------------------------- #
# LLM RANK (5 SITES MAX + MOCK)
# -------------------------- #
def rank_sites(sites):
    if not llm:
        st.warning("Using mock scores")
        return [
            {"name": s["name"], "score": 95 if "Virginia" in s["name"] else 88 if "Texas" in s["name"] else 82 if "Salt" in s["name"] else 75 if "Phoenix" in s["name"] else 70, 
             "justification": f"Mock: {s['name']} - Good power & low risk"} 
            for s in sites
        ]
    
    clean_sites = [clean(s) for s in sites][:5]  # MAX 5
    
    try:
        resp = llm.invoke(prompt_batch.format_prompt(sites=str(clean_sites)).to_messages())
        raw = str(resp.content).strip()
        st.info(f"Raw: {raw[:200]}...")
        
        parsed = extract_json(raw)
        if parsed and isinstance(parsed, list) and len(parsed) > 0:
            st.success(f"AI ranked {len(parsed)} sites!")
            return parsed
        else:
            st.error("AI returned invalid JSON")
            return [{"name": s["name"], "score": 30, "justification": "Invalid JSON"} for s in sites]
            
    except Exception as e:
        st.error(f"API Error: {type(e).__name__}: {e}")
        return [{"name": s["name"], "score": 30, "justification": "API failed"} for s in sites]

# -------------------------- #
# UI + MAP + MARKERS
# -------------------------- #
st.set_page_config(page_title="DC Site Scout", layout="wide")
st.title("DC Site Scout")
st.markdown("**Upload GeoJSON → GEE → AI Rank → Map**")

uploaded = st.file_uploader("Upload GeoJSON", type=["geojson"])

if uploaded:
    with st.spinner("Sampling..."):
        st.session_state.sites = []
        bounds = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        geo = json.load(uploaded)
        for f in geo["features"]:
            g = ee.Geometry(f["geometry"])
            c = g.centroid().getInfo()["coordinates"]
            site = {"name": f["properties"]["name"], "lat": c[1], "lon": c[0]}
            site.update(sample(g))
            st.session_state.sites.append(site)
            for coord in f["geometry"]["coordinates"][0]:
                bounds[0] = min(bounds[0], coord[0])
                bounds[1] = min(bounds[1], coord[1])
                bounds[2] = max(bounds[2], coord[0])
                bounds[3] = max(bounds[3], coord[1])
        st.session_state.bounds = bounds

@st.cache_resource
def get_map():
    if "bounds" in st.session_state:
        b = st.session_state.bounds
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
        m = geemap.Map(center=center, zoom=4)
    else:
        m = geemap.Map(center=[38, -98], zoom=4)
    m.add_basemap("HYBRID")
    Draw(export=False, draw_options={
        "polyline": False, "rectangle": True, "circle": False,
        "marker": True, "circlemarker": False, "polygon": True
    }).add_to(m)
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

# MARKERS WITH COLOR
for site in st.session_state.get("sites", []):
    score_obj = next((r for r in st.session_state.get("ranked_results", []) if r["name"] == site["name"]), None)
    score = score_obj["score"] if score_obj else None
    
    color = "green" if score and score >= 80 else "orange" if score and score >= 60 else "red"
    
    popup = f"<b>{site['name']}</b><br>Score: <b>{score or 'N/A'}</b><br>Power: {site.get('power_km', 'N/A')} km<br>Flood: {site.get('flood_pct', 'N/A')}%"
    m.add_marker(
        location=[site["lat"], site["lon"]],
        popup=popup,
        tooltip=site["name"],
        icon=geemap.folium.Icon(color=color, icon="info-sign")
    )

# RANKING PANEL
with col_rank:
    st.markdown("### AI Rankings")
    if st.session_state.get("ranked"):
        for r in st.session_state.ranked_results:
            st.write(f"**{r['name']}** – **{r['score']}** – {r['justification']}")
    else:
        st.info("Upload to start")