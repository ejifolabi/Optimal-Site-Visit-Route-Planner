import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="Smart Site Visit Route", layout="wide")

st.title("📍 Smart Site Visit Route Planner")
st.markdown("Upload an Excel file containing site coordinates: **Latitude, Longitude, Address** (case-insensitive).")

# Upload Excel file
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

start_lat = st.text_input("Optional Start Latitude", placeholder="e.g. 6.5244")
start_lon = st.text_input("Optional Start Longitude", placeholder="e.g. 3.3792")

@st.cache_data
def read_data(file):
    df = pd.read_excel(file)
    col_map = {col.lower(): col for col in df.columns}
    required = ['latitude', 'longitude', 'address']

    if not all(col in col_map for col in required):
        st.error(f"Your Excel must contain columns: {required}")
        return None

    df.rename(columns={
        col_map['latitude']: 'lat',
        col_map['longitude']: 'lon',
        col_map['address']: 'address'
    }, inplace=True)

    # Drop rows with missing coordinates
    df.dropna(subset=['lat', 'lon'], inplace=True)

    return df[['lat', 'lon', 'address']]

@st.cache_data
def compute_closest_path(df, user_start=None):
    visited = []
    path = []
    total_distance = 0.0

    if user_start:
        current_point = user_start
        path.append({
            "address": "User Start",
            "lat": current_point[0],
            "lon": current_point[1],
            "distance_km": 0
        })
    else:
        first = df.iloc[0]
        current_point = (first['lat'], first['lon'])
        visited.append(0)
        path.append({
            "address": first['address'],
            "lat": first['lat'],
            "lon": first['lon'],
            "distance_km": 0
        })

    while len(visited) < len(df):
        min_dist = float('inf')
        next_index = -1
        for i, row in df.iterrows():
            if i in visited:
                continue
            dist = geodesic(current_point, (row['lat'], row['lon'])).km
            if dist < min_dist:
                min_dist = dist
                next_index = i

        visited.append(next_index)
        next_site = df.iloc[next_index]
        current_point = (next_site['lat'], next_site['lon'])
        total_distance += min_dist
        path.append({
            "address": next_site['address'],
            "lat": next_site['lat'],
            "lon": next_site['lon'],
            "distance_km": round(min_dist, 2)
        })

    return path, round(total_distance, 2)

if uploaded_file:
    df = read_data(uploaded_file)
    if df is not None and not df.empty:
        st.success(f"{len(df)} locations loaded successfully.")

        # Validate user input for optional start
        if start_lat and start_lon:
            try:
                user_start_coords = (float(start_lat), float(start_lon))
            except:
                st.warning("Invalid coordinates provided. Starting from the first location.")
                user_start_coords = None
        else:
            user_start_coords = None

        with st.spinner("Calculating optimized route..."):
            path, total_distance = compute_closest_path(df, user_start=user_start_coords)

        st.subheader("📍 Visit Order by Closest Proximity")
        path_df = pd.DataFrame(path)
        st.dataframe(path_df[["address", "distance_km"]].rename(columns={"distance_km": "Distance (km)"}))

        st.success(f"✅ Total estimated travel distance: **{total_distance} km**")

        # Debugging coordinates
        st.write("### Debug: Coordinates Used")
        for point in path:
            st.write(f"{point['address']}: ({point['lat']}, {point['lon']})")

        # Show route on map
        st.subheader("🗺️ Route Map")
        try:
            route_map = folium.Map(location=[path[0]["lat"], path[0]["lon"]], zoom_start=12)

            # Start marker
            folium.Marker(
                [path[0]["lat"], path[0]["lon"]],
                popup="Start",
                icon=folium.Icon(color="green")
            ).add_to(route_map)

            # Route markers and lines
            for i, point in enumerate(path[1:], start=1):
                folium.Marker(
                    [point["lat"], point["lon"]],
                    popup=f"{i}. {point['address']} ({point['distance_km']} km)",
                    icon=folium.Icon(color="blue")
                ).add_to(route_map)

                folium.PolyLine(
                    [(path[i - 1]["lat"], path[i - 1]["lon"]),
                     (point["lat"], point["lon"])],
                    color="blue"
                ).add_to(route_map)

            st_folium(route_map, width=1000, height=550)

        except Exception as e:
            st.error("An error occurred while displaying the map.")
            st.exception(e)

    else:
        st.error("Failed to load data from the uploaded file.")
