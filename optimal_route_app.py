import streamlit as st
import pandas as pd
import openrouteservice
from geopy.distance import geodesic
from streamlit_folium import st_folium
import folium

# --- Streamlit Config ---
st.set_page_config(page_title="Optimal Site Visit Route", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")
st.markdown("Upload an Excel file with **Latitude**, **Longitude**, and **Address** columns (case-insensitive).")

# --- ORS API Client ---
@st.cache_resource
def get_ors_client():
    return openrouteservice.Client(key=st.secrets["ORS_API_KEY"])

client = get_ors_client()

# --- Helper: Normalize Column Names ---
def normalize_columns(df):
    df.columns = [col.lower().strip() for col in df.columns]
    required = {"latitude", "longitude", "address"}
    if not required.issubset(set(df.columns)):
        st.error("Excel must contain columns: Latitude, Longitude, Address")
        st.stop()
    return df.rename(columns={"latitude": "Latitude", "longitude": "Longitude", "address": "Address"})

# --- Helper: Get Road Distance ---
@st.cache_data(show_spinner=False)
def get_road_distance(client, coord1, coord2):
    try:
        route = client.directions(coordinates=[coord1, coord2], profile='driving-car', format='geojson')
        meters = route['features'][0]['properties']['segments'][0]['distance']
        return meters / 1000  # in KM
    except Exception:
        return float('inf')

# --- Get Closest Location Chain ---
def get_closest_chain(df, start_coords):
    visited = []
    unvisited = df.copy()
    current_coords = start_coords
    total_km = 0

    while not unvisited.empty:
        distances = unvisited.apply(
            lambda row: get_road_distance(client, (current_coords[1], current_coords[0]), (row["Longitude"], row["Latitude"])),
            axis=1
        )
        min_idx = distances.idxmin()
        min_row = unvisited.loc[min_idx]
        min_dist = distances[min_idx]
        total_km += min_dist
        visited.append({
            "Address": min_row["Address"],
            "Latitude": min_row["Latitude"],
            "Longitude": min_row["Longitude"],
            "Distance_from_last": round(min_dist, 2)
        })
        current_coords = (min_row["Latitude"], min_row["Longitude"])
        unvisited = unvisited.drop(min_idx)

    return visited, round(total_km, 2)

# --- Upload Excel ---
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = normalize_columns(df)

    with st.expander("Optional: Enter Starting Location"):
        col1, col2 = st.columns(2)
        with col1:
            user_lat = st.number_input("Your Latitude (optional)", format="%.6f")
        with col2:
            user_lon = st.number_input("Your Longitude (optional)", format="%.6f")

    if st.button("🧭 Plan Route"):
        if "route" not in st.session_state:
            if user_lat and user_lon:
                start_coords = (user_lat, user_lon)
            else:
                first_row = df.iloc[0]
                start_coords = (first_row["Latitude"], first_row["Longitude"])

            with st.spinner("Calculating optimal route..."):
                route, total_distance = get_closest_chain(df, start_coords)
                st.session_state["route"] = route
                st.session_state["total_km"] = total_distance

    if "route" in st.session_state:
        st.success(f"🛣️ Route ready! Total travel distance: **{st.session_state['total_km']} km**")

        # Show Table
        result_df = pd.DataFrame(st.session_state["route"])
        result_df.index += 1
        st.subheader("📍 Visit Order by Closest Road Distance")
        st.dataframe(result_df)

        # Map Display
        m = folium.Map(location=[result_df["Latitude"].iloc[0], result_df["Longitude"].iloc[0]], zoom_start=12, tiles="cartodbpositron")
        for idx, row in result_df.iterrows():
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=f"{idx}. {row['Address']}\n({row['Distance_from_last']} km)",
                icon=folium.Icon(color="blue", icon="map-marker")
            ).add_to(m)

        st.subheader("🗺️ Route Map")
        st_folium(m, width=1200, height=600)
