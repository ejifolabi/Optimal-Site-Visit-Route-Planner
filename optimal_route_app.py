import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium, folium_static
import time

st.set_page_config(page_title="Optimal Site Visit Route Planner", layout="wide")
st.title("🚗 Optimal Road Route Planner - Real Nigerian Roads")

st.markdown("**Upload Excel**: Latitude, Longitude, Address (case-insensitive). Optional S/N column.")

# File upload
uploaded_file = st.file_uploader("📁 Upload Excel File", type=["xlsx"])

# User location
with st.expander("📍 Your Current Location (Onitsha/Birnin Kebbi)"):
    user_lat = st.number_input("Latitude (Nigeria: 4-15°N)", value=6.1520, format="%.6f")
    user_lon = st.number_input("Longitude (Nigeria: 2-15°E)", value=6.7850, format="%.6f")
    use_user_location = st.checkbox("Start from my location", value=False)

@st.cache_data(ttl=3600)
def get_road_distance(coord1, coord2):
    """OSRM real road distance (free, Nigeria coverage)."""
    try:
        lon1, lat1 = coord1[1], coord1[0]
        lon2, lat2 = coord2[1], coord2[0]
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        
        resp = requests.get(url, timeout=8)
        data = resp.json()
        
        if data.get('code') == 'Ok' and data.get('routes'):
            return data['routes'][0]['distance'] / 1000  # meters to km
        else:
            st.warning(f"🚧 OSRM routing failed, using straight-line: {coord1} → {coord2}")
            return geodesic(coord1, coord2).km
            
    except Exception as e:
        st.warning(f"🌐 Network error, using straight-line backup")
        return geodesic(coord1, coord2).km

def find_road_greedy_route(start, points_df):
    """Road-optimized greedy nearest neighbor."""
    points = points_df.copy()
    visited_indices = []
    current = start
    remaining_indices = list(range(len(points)))
    total_calls = 0

    st.info(f"🛣️ Computing **real road distances** for {len(points)} sites...")

    progress_bar = st.progress(0)
    status_text = st.empty()

    while remaining_indices:
        # Real-time progress
        progress = 1 - len(remaining_indices) / len(points)
        progress_bar.progress(progress)
        status_text.text(f"Routing... {len(visited_indices)+1}/{len(points)} sites")

        # Calculate road distances to remaining sites
        distances = []
        for i in remaining_indices:
            coord = (points.iloc[i]['Latitude'], points.iloc[i]['Longitude'])
            dist = get_road_distance(current, coord)
            distances.append((i, dist))
            total_calls += 1

        # Nearest by ROAD distance
        next_idx = min(distances, key=lambda x: x[1])[0]
        visited_indices.append(next_idx)
        current = (points.iloc[next_idx]['Latitude'], points.iloc[next_idx]['Longitude'])
        remaining_indices.remove(next_idx)

    st.success(f"✅ Route optimized! {total_calls} road distance calculations.")
    return points.iloc[visited_indices].reset_index(drop=True)

if uploaded_file:
    try:
        with st.spinner("📊 Reading Excel..."):
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.lower().str.strip()

        # Column validation
        required_cols = {"latitude", "longitude", "address"}
        missing = required_cols - set(df.columns)
        if missing:
            st.error(f"❌ Missing columns: {', '.join(missing)}")
            st.stop()

        # Standardize column names
        df = df.rename(columns={
            "latitude": "Latitude", 
            "longitude": "Longitude", 
            "address": "Address",
            "s/n": "S/N"
        })

        # Nigeria coordinate validation (Kebbi/Onitsha focus)
        df = df[(df['Latitude'].between(4, 15)) & (df['Longitude'].between(2, 15))]
        if df.empty:
            st.error("❌ No valid Nigeria coordinates found (4-15°N, 2-15°E)")
            st.stop()

        df = df.dropna(subset=["Latitude", "Longitude", "Address"])
        if len(df) < 1:
            st.error("❌ No valid sites after cleaning.")
            st.stop()

        has_sn = "S/N" in df.columns
        locations = df

        # Starting point
        if use_user_location and abs(user_lat) > 0.1:
            start_point = (user_lat, user_lon)
            start_name = f"Your Location (Onitsha area)"
            st.info(f"🚗 Starting from your location: {start_name}")
        else:
            start_point = (df.iloc[0]['Latitude'], df.iloc[0]['Longitude'])
            start_name = df.iloc[0]['Address']

        # CRITICAL: ROAD ROUTING
        ordered_df = find_road_greedy_route(start_point, locations)

        # Calculate route with road distances
        total_distance = 0.0
        route_coords = [start_point]
        display_data = []
        current_point = start_point

        # Add starting point
        row0 = {
            "S/N": "" if has_sn else None,
            "Latitude": start_point[0], 
            "Longitude": start_point[1], 
            "Address": start_name, 
            "Road Distance (km)": 0.0,
            "Est. Time": "Start"
        }
        display_data.append(row0)

        with st.spinner("📏 Final distance calculations..."):
            for idx, loc in ordered_df.iterrows():
                site_coord = (loc["Latitude"], loc["Longitude"])
                distance = get_road_distance(current_point, site_coord)
                total_distance += distance
                route_coords.append(site_coord)

                minutes = distance / 50 * 60  # 50km/h Nigeria roads
                row = {
                    "S/N": loc.get("S/N", f"Site {idx+1}"),
                    "Latitude": loc["Latitude"], 
                    "Longitude": loc["Longitude"], 
                    "Address": loc["Address"][:40] + "..." if len(str(loc["Address"])) > 40 else loc["Address"],
                    "Road Distance (km)": round(distance, 1),
                    "Est. Time": f"{round(minutes, 0)} min"
                }
                display_data.append(row)
                current_point = site_coord

        # RESULTS DASHBOARD
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🛣️ Total Road Distance", f"{round(total_distance, 1)} km")
        with col2:
            st.metric("📍 Sites", len(ordered_df))
        with col3:
            st.metric("⏱️ Est. Total Time", f"{round(total_distance/50*60, 0)} min")
        with col4:
            st.metric("🚙 Avg Speed", "50 km/h")

        # Route table
        st.subheader("📋 Visit Order (Road Optimized)")
        st.dataframe(pd.DataFrame(display_data), use_container_width=True)

        # INTERACTIVE MAP
        st.subheader("🗺️ Real Road Route Map")
        m = folium.Map(location=route_coords[0], zoom_start=11, tiles="CartoDB positron")

        # Add markers
        for i, coord in enumerate(route_coords):
            label = display_data[i]["S/N"] if display_data[i]["S/N"] else display_data[i]["Address"][:20]
            color = "green" if i == 0 else "blue"
            folium.Marker(
                coord, 
                popup=f"Stop {i+1}: {display_data[i]['Address']}",
                tooltip=label,
                icon=folium.Icon(color=color, icon="truck" if i == 0 else "info-sign")
            ).add_to(m)

        # Red route line
        folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)

        # Map display with fallback
        try:
            st_folium(m, width=1200, height=600, returned_objects=[])
        except:
            st.warning("⚠️ Interactive map failed—using static")
            folium_static(m, width=1200, height=600)

        # Export
        csv = pd.DataFrame(display_data).to_csv(index=False)
        st.download_button("💾 Download Route (CSV)", csv, "kebbi_site_route.csv")

    except Exception as e:
        st.error(f"💥 Error: {str(e)}")
        st.exception(e)

st.caption("⚡ Powered by OSRM - Real Nigerian road distances")
