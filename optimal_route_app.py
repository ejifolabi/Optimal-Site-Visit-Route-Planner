import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import openrouteservice
from openrouteservice import convert

st.set_page_config(page_title="📍 Smart Site Visit Route", layout="wide")

st.title("📍 Smart Site Visit Route Planner")
st.markdown("Upload an Excel file containing site coordinates: **Latitude, Longitude, Address** (case-insensitive).")

# --- Caching client creation
@st.cache_resource
def get_ors_client():
    return openrouteservice.Client(key=st.secrets["ORS_API_KEY"])

# --- Optional: Get user's location
with st.expander("🔍 Optional: Enter Your Current Location (Latitude, Longitude)"):
    user_lat = st.number_input("Your Latitude", format="%.6f")
    user_lon = st.number_input("Your Longitude", format="%.6f")
    use_user_location = st.checkbox("Use as starting point")

# --- Upload section
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# --- Start processing
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Normalize columns
    df.columns = df.columns.str.lower()
    required_cols = {"latitude", "longitude", "address"}
    if not required_cols.issubset(set(df.columns)):
        st.error(f"Your Excel must contain: {required_cols}")
        st.stop()

    df = df.rename(columns={
        "latitude": "lat",
        "longitude": "lon",
        "address": "address"
    })

    # --- Starting point
    if use_user_location:
        start_coords = (user_lat, user_lon)
    else:
        start_coords = (df.iloc[0]["lat"], df.iloc[0]["lon"])

    # --- Calculate distance from starting point
    @st.cache_data
    def sort_by_proximity(df, start_coords):
        df["distance_from_start_km"] = df.apply(
            lambda row: geodesic(start_coords, (row["lat"], row["lon"])).km, axis=1)
        return df.sort_values("distance_from_start_km").reset_index(drop=True)

    sorted_df = sort_by_proximity(df, start_coords)

    # --- Display sorted addresses and distances
    st.subheader("📄 Locations Sorted by Proximity")
    st.dataframe(sorted_df[["address", "lat", "lon", "distance_from_start_km"]].round(3))

    # --- Compute route using ORS
    with st.spinner("Calculating route using OpenRouteService..."):
        coords = [[row["lon"], row["lat"]] for _, row in sorted_df.iterrows()]
        if use_user_location:
            coords.insert(0, [user_lon, user_lat])

        client = get_ors_client()
        try:
            route = client.directions(
                coordinates=coords,
                profile='driving-car',
                format='geojson'
            )
        except Exception as e:
            st.error("🚨 ORS API Error: " + str(e))
            st.stop()

    # --- Compute total distance
    total_distance_km = sum(geodesic(
        (coords[i][1], coords[i][0]), (coords[i+1][1], coords[i+1][0])
    ).km for i in range(len(coords)-1))

    st.success(f"✅ Total Route Distance: **{total_distance_km:.2f} km**")

    # --- Map section
    st.subheader("🗺️ Route Map")
    center_lat = sum([c[1] for c in coords]) / len(coords)
    center_lon = sum([c[0] for c in coords]) / len(coords)
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    # Plot route
    folium.GeoJson(route, name="Route").add_to(m)

    # Markers
    for i, point in enumerate(coords):
        label = "Start" if i == 0 else f"Stop {i}"
        folium.Marker(
            location=[point[1], point[0]],
            popup=label,
            icon=folium.Icon(color="green" if i == 0 else "blue", icon="flag")
        ).add_to(m)

    st_folium(m, width=1100, height=600)
