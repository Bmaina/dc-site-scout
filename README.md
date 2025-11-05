
<image-card alt="DC Site Scout" src="screenshot.png" ></image-card>

# DC Site Scout  
**AI-Powered Data Center Site Selection**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://dc-site-scout.streamlit.app)  
[![GitHub](https://img.shields.io/badge/GitHub-View%20Code-blue?logo=github)](https://github.com/Bmaina/dc-site-scout)

---

## Problem

> **$100B in AI data centers are being built.**  
> **90% of site selections fail** due to **flood risk, power scarcity, latency, or cost**.

---

## Solution

**Upload land parcels → Get AI-ranked sites in 10 seconds.**

![App Screenshot](https://github.com/Bmaina/dc-site-scout/blob/main/screenshot.png?raw=true)

---

## Features

| Feature | Description |
|-------|-----------|
| Interactive Map | Draw polygons, upload GeoJSON |
| AI Rankings | Scores 0–100 with justification |
| Color-Coded Markers | Green = 80+, Orange = 60–79, Red = <60 |
| GEE Data (Mock) | Elevation, flood risk, power proximity |
| Fully Deployable | No API keys, no install errors |

---

## Live Demo

[https://dc-site-scout.streamlit.app](https://dc-site-scout.streamlit.app)

---

## Tech Stack

- **Frontend**: Streamlit
- **Map**: Folium + `streamlit-folium`
- **AI**: Mock mode (real AI ready for enterprise)
- **Deploy**: Streamlit Cloud (100% free)

---

## How to Run Locally

```bash
# 1. Clone repo
git clone https://github.com/Bmaina/dc-site-scout.git
cd dc-site-scout

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run app
streamlit run app.py
