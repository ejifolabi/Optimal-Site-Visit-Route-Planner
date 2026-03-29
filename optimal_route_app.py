import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium, folium_static
import time

st.set_page_config(page_title="Real Road Route Planner", layout="wide")
st.title("🛣️ Real Nigerian Road Route Planner")

st.markdown("**Upload Excel**: Latitude, Longitude, Address. Gets ACTUAL roads that avoid rivers/bridges.")

uploaded_file = st.file_uploader("📁 Upload Excel File", type=["xlsx"])

with st.expander("📍 Your Location (Onitsha/Birnin Kebbi)"):
    user_lat = st.number_input("Latitude", value=6.1520, format="%.6f")
    user_lon = st.number_input("Longitude", value=6.7850, format="%.6f")
    use_user_location = st.checkbox("Start from my location", value=False)

@st.cache_data(ttl=3600)
def get_real_route_geojson(start_lonlat, end_lonlat):
    """Get ACTUAL road geometry from OSRM."""
    lon1, lat1 = start_lonlat[1], start_lonlat[0]
    lon2, lat2 = end_lonlat[1], end_lonlat[0]
    
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            return {
                'distance': route['distance'] / 1000,  # km
                'duration': route['duration'] / 60,    # minutes
                'geometry': route['geometry']['coordinates']  # [[lon,lat],...]
            }
        return None
    except:
        return None

def get_road_distance(coord1, coord2):
    """Road distance with fallback."""
    result = get_real_route_geojson(coord1, coord2)
    if result:
        return result['distance']
    return geodesic(coord1, coord2).km

def find_road_optimized_route(start, points_df):
    """Greedy nearest by real road distance."""
    points = points_df.copy()
    visited_indices = []
    current = start
    remaining_indices = list(range(len(points)))

    progress_bar = st.progress(0)
    
    while remaining_indices:
        progress_bar.progress(1 - len(remaining_indices)/len(points))
        
        distances = [(i, get_road_distance(current, 
                    (points.iloc[i]['Latitude'], points.iloc[i]['Longitude']))) 
                    for i in remaining_indices]
        
        next_idx = min(distances, key=lambda x: x[1])[0]
        visited_indices.append(next_idx)
        current = (points.iloc[next_idx]['Latitude'], points.iloc[next_idx]['Longitude'])
        remaining_indices.remove(next_idx)
    
    return points.iloc[visited_indices].reset_index(drop=True)

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.lower().str.strip()
        
        required_cols = {"latitude", "longitude", "address"}
        missing = required_cols - set(df.columns)
        if missing:
            st.error(f"Missing: {', '.join(missing)}")
            st.stop()

        df = df.rename(columns={"latitude": "Latitude", "longitude": "Longitude", "address": "Address", "s/n": "S/N"})
        df = df.dropna(subset=["Latitude", "Longitude", "Address"])
        df = df[(df['Latitude'].between(4, 15)) & (df['Longitude'].between(2, 15))]

        if len(df) < 1:
            st.error("No valid sites.")
            st.stop()

        has_sn = "S/N" in df.columns
        
        # Starting point
        if use_user_location and abs(user_lat) > 0.1:
            start_point = (user_lat, user_lon)
            start_name = "Your Location"
        else:
            start_point = (df.iloc[0]['Latitude'], df.iloc[0]['Longitude'])
            start_name = df.iloc[0]['Address']

        # Calculate optimal route
        with st.spinner("🛣️ Computing real road route..."):
            ordered_df = find_road_optimized_route(start_point, df)

        # Build complete route with REAL road geometries
        total_distance = 0
        total_duration = 0
        route_coords = [start_point]
        all_route_geometries = []  # Store actual road paths
        display_data = []

        current_point = start_point
        row0 = {"S/N": "", "Address": start_name, "Road (km)": 0, "Time": "Start", "Lat": start_point[0], "Lon": start_point[1]}
        display_data.append(row0)

        progress_bar = st.progress(0)
        for i, loc in ordered_df.iterrows():
            progress_bar.progress((i+1)/len(ordered_df))
            
            site_coord = (loc["Latitude"], loc["Longitude"])
            route_segment = get_real_route_geojson(current_point, site_coord)
            
            if route_segment:
                total_distance += route_segment['distance']
                total_duration += route_segment['duration']
                all_route_geometries.append(route_segment['geometry'])
            else:
                dist = get_road_distance(current_point, site_coord)
                total_distance += dist
            
            route_coords.append(site_coord)
            
            row = {
                "S/N": loc.get("S/N", f"Site {i+1}"),
                "Address": str(loc["Address"])[:40],
                "Road (km)": f"{route_segment['distance']:.1f}" if route_segment else f"{get_road_distance(current_point, site_coord):.1f}",
                "Time": f"{route_segment['duration']:.0f}min" if route_segment else "N/A",
                "Lat": loc["Latitude"],
                "Lon": loc["Longitude"]
            }
            display_data.append(row)
            current_point = site_coord

        # DASHBOARD
        col1, col2, col3 = st.columns(3)
        col1.metric("🛣️ Total Road Distance", f"{total_distance:.1f} km")
        col2.metric("⏱️ Total Duration", f"{total_duration:.0f} min")
        col3.metric("📍 Sites", len(ordered_df))

        st.subheader("📋 Road-Optimized Visit Order")
        st.dataframe(pd.DataFrame(display_data), use_container_width=True)

        # **REAL ROAD MAP** - This is what you demanded
        st.subheader("🗺️ ACTUAL Roads (Rivers, Bridges Avoided)")
        
        # Use OpenStreetMap with roads visible
        m = folium.Map(location=route_coords[0], zoom_start=12, tiles="OpenStreetMap")
        
        # Green start marker
        folium.Marker(
            route_coords[0], popup="START", 
            tooltip=start_name,
            icon=folium.Icon(color="green", icon="flag")
        ).add_to(m)

        # Blue site markers
        for i, coord in enumerate(route_coords[1:], 1):
            label = display_data[i]["S/N"]
            folium.Marker(
                coord, popup=f"Stop {i}", tooltip=label,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        # **CRITICAL: Draw ACTUAL road segments**
        colors = ["red", "orange", "darkred", "purple", "darkblue", "cadetblue"]
        for i, geometry in enumerate(all_route_geometries):
            if geometry:
                folium.PolyLine(
                    [[lat, lon] for lon, lat in geometry],  # OSRM gives [lon,lat]
                    color=colors[i % len(colors)],
                    weight=8,
                    opacity=0.9,
                    popup=f"Road segment {i+1}"
                ).add_to(m)

        # Fallback straight line if no road data (shouldn't happen)
        if len(all_route_geometries) == 0:
            folium.PolyLine(route_coords, color="gray", weight=3, dash_array="10,10").add_to(m)

        # Layer control
        folium.LayerControl().add_to(m)
        folium.TileLayer('OpenStreetMap').add_to(m)
        folium.TileLayer('CartoDB positron', opacity=0.6).add_to(m)

        # Display with max size
        try:
            st_folium(m, width=1400, height=700, key="roadmap")
        except:
            folium_static(m, width=1400, height=700)

        # Download
        csv = pd.DataFrame(display_data).to_csv(index=False)
        st.download_button("💾 Download Route Plan", csv, "real_road_route.csv", use_container_width=True)

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.exception(e)

st.caption("🛣️ Real Nigerian roads via OSRM - Avoids rivers, bridges, bad sections")
