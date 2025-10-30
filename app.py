import os
import json
import streamlit as st
import ee
from folium.plugins import Draw 
import geemap.foliumap as geemap
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from streamlit_folium import folium_static # Map rendering fix
import io 

# --------------------------
# 🌍 EARTH ENGINE SETUP
# --------------------------
@st.cache_resource
def init_earth_engine():
    try:
        ee.Initialize()
        return True
    except Exception as e:
        st.error(f"Earth Engine initialization failed. Error: {e}")
        return False

if not init_earth_engine():
    st.stop()


# --------------------------
# 🔑 LLM SETUP
# --------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") 
if not ANTHROPIC_API_KEY:
    st.error("🚨 Missing Anthropic API key. Set **ANTHROPIC_API_KEY** in your environment.")
    st.stop()
llm = ChatAnthropic(model="claude-instant-1.2", api_key=ANTHROPIC_API_KEY)

# --------------------------
# 📝 PROMPT TEMPLATES 
# --------------------------
system_prompt_single = SystemMessagePromptTemplate.from_template("You are a data center site selection expert.")
human_prompt_single = HumanMessagePromptTemplate.from_template("Given this site data {site_data}, assess its suitability for a data center considering power access, flood risk, latency, and cost. Provide a score (0-100) and a brief justification. Return output as JSON: {{'score': <number>, 'justification': <string>}}")
prompt_single = ChatPromptTemplate.from_messages([system_prompt_single, human_prompt_single])

system_prompt_batch = SystemMessagePromptTemplate.from_template("You are a data center site selection expert.")
human_prompt_batch = HumanMessagePromptTemplate.from_template("Given these sites {sites_data}, rank them from best to worst for data center suitability considering power access, flood risk, latency, and cost. Return a JSON array of objects: [{{'name': <site_name>, 'score': <0-100>, 'justification': <text>}}, ...]")
prompt_batch = ChatPromptTemplate.from_messages([system_prompt_batch, human_prompt_batch])

# --------------------------
# 🌄 UTILITY FUNCTION TO SAMPLE EARTH ENGINE DATA 
# --------------------------
def sample_site_data(geom):
    """Sample elevation and population density for a given geometry using Earth Engine."""
    site_data = {}
    try:
        elevation_dict = ee.Image("USGS/SRTMGL1_003").reduceRegion(reducer=ee.Reducer.mean(), geometry=geom, scale=30).getInfo()
        site_data["elevation_m"] = round(elevation_dict.get("elevation", 0), 2)
    except Exception:
        site_data["elevation_m"] = None
    try:
        pop_dict = ee.Image("CIESIN/GPWv411/GPW_Population_Density").reduceRegion(reducer=ee.Reducer.mean(), geometry=geom, scale=1000).getInfo()
        site_data["pop_density"] = round(pop_dict.get("population_density", 0), 2)
    except Exception:
        site_data["pop_density"] = None
    return site_data

# --------------------------
# 🌐 STREAMLIT APP UI
# --------------------------
st.set_page_config(page_title="DC Site Scout Visual", layout="wide")
st.title("🏗️ DC Site Scout: Visual AI Ranking")
st.markdown(
    "**NOTE:** Drawing support is currently disabled due to package version conflicts. Please **upload a GeoJSON file** instead. "
    "Scores are color-coded on the map."
)

col1, col2 = st.columns([2, 1])

# --------------------------
# 🗺️ INTERACTIVE MAP (RENDERING)
# --------------------------

@st.cache_resource
def get_geemap():
    m = geemap.Map(center=[20, 0], zoom=2)
    m.add_basemap("HYBRID")
    Draw(export=False).add_to(m) 
    return m

with col1:
    m = get_geemap() 
    
    # Initial map display placeholder
    map_placeholder = st.empty()
    map_placeholder.info("Loading map...")
    
    # Placeholder variable
    drawn_features_json = None 

# --------------------------
# 📥 GEOJSON UPLOAD LOGIC 
# --------------------------
with col2:
    st.markdown("### 📥 Upload Site Data (GeoJSON)")
    uploaded_file = st.file_uploader(
        "Upload a GeoJSON file containing site polygons/points.",
        type=["geojson"]
    )

    if uploaded_file is not None and uploaded_file.name != st.session_state.get('last_uploaded_file', ''):
        
        bytes_data = uploaded_file.getvalue()
        geojson_data = json.load(io.BytesIO(bytes_data))
        
        # Reset session state for new upload
        st.session_state['drawn_sites'] = []
        st.session_state['site_scores'] = {}
        new_sites_count = 0

        if "features" in geojson_data:
            for i, f in enumerate(geojson_data["features"]):
                try:
                    geom = ee.Geometry(f["geometry"])
                    coords = geom.centroid().getInfo()["coordinates"]

                    site = {
                        "id": i + 1,
                        "name": f["properties"].get("name", f"Uploaded Site {i+1}"),
                        "lat": coords[1],
                        "lon": coords[0],
                    }
                    
                    with st.spinner(f"Sampling data for {site['name']}..."):
                        site.update(sample_site_data(geom))
                    
                    st.session_state['drawn_sites'].append(site)
                    new_sites_count += 1
                    
                except Exception as e:
                    st.warning(f"Failed to process feature {i+1} from GeoJSON: {e}")
        
        st.success(f"Successfully loaded {new_sites_count} sites!")
        
        st.session_state['last_uploaded_file'] = uploaded_file.name
        st.rerun() # IMPORTANT: Forces script rerun to refresh sidebar/map


# --------------------------
# ⚙️ PROCESS LOADED FEATURES (SIDEBAR AND MARKERS)
# --------------------------
# Initialize session state variables if they don't exist
if 'drawn_sites' not in st.session_state:
    st.session_state['drawn_sites'] = []
if 'site_scores' not in st.session_state:
    st.session_state['site_scores'] = {}
    
def run_single_site(site):
    response = llm.invoke(prompt_single.format_prompt(site_data=str(site)).to_messages())
    try:
        return json.loads(str(response.content).replace("'", '"'))
    except Exception:
        return {"raw_response": str(response.content)}

def run_batch_sites(sites):
    response = llm.invoke(prompt_batch.format_prompt(sites_data=str(sites)).to_messages())
    try:
        return json.loads(str(response.content).replace("'", '"'))
    except Exception:
        return {"raw_response": str(response.content)}

# --- LOGIC TO RENDER SIDEBAR UI ---
if st.session_state['drawn_sites']:
    
    # DEBUG LINE ADDED HERE
    st.sidebar.text(f"DEBUG: Found {len(st.session_state['drawn_sites'])} sites.") 
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 AI Ranking Controls")
    
    # Display individual rank buttons
    for site in st.session_state['drawn_sites']:
        if st.sidebar.button(f"Rank {site['name']}"):
            st.subheader(f"🏆 AI Ranking for {site['name']}")
            response_json = run_single_site(site)
            st.write(response_json)
            st.session_state['site_scores'][site["name"]] = response_json.get("score", None)
            st.rerun() # Rerun to update the marker color immediately

    # Display batch rank button
    if st.sidebar.button("Rank All Sites"):
        st.subheader("🏆 AI Ranking: All Sites")
        response_json = run_batch_sites(st.session_state['drawn_sites'])
        st.write(response_json)
        if isinstance(response_json, list):
            for s in response_json:
                st.session_state['site_scores'][s["name"]] = s.get("score", None)
        st.rerun() # Rerun to update the marker colors immediately

    # --- MARKER ADDITION AND FINAL MAP RENDERING ---
    
    # 1. Add markers to the map object (m)
    for site in st.session_state['drawn_sites']:
        score = st.session_state['site_scores'].get(site["name"], None)
        color = ("green" if score is not None and score >= 80 else
                 "orange" if score is not None and score >= 60 else
                 "red" if score is not None else
                 "blue")
        m.add_marker(
            location=[site["lat"], site["lon"]],
            popup=(f"**{site['name']}**<br>Score: **{score if score is not None else 'N/A'}**"),
            tooltip=site["name"],
            icon=geemap.folium.Icon(color=color, icon='info-sign'))

# 2. Render the map in the main column (col1)
with col1:
    # Clear the initial loading message and show the final map
    map_placeholder.empty()
    folium_static(m)