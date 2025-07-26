import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(page_title="Optimal Site Visit Route Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")

st.markdown("Upload an Excel file with columns: **Latitude, Longitude, Address** (case-insensitive).")

# Upload
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# Optional: user current location
with st.expander("📍 Optional: Enter Your Current Location"):
    user_lat = st.number_input("Your Latitude", value=0.0, format="%.6f")
    user_lon = st.number_input("Your Longitude", value=0.0, format="%.6f")
    use_user_location = st.checkbox("Use my location as starting point", value=False)

# Distance calculation
def calculate_distance(coord1, coord2):
    return geodesic(coord1, coord2).km

# Greedy nearest neighbor ordering
def find_greedy_route(start, points):
    visited = []
    current = start
    remaining = points.copy()

    while remaining:
        next_point = min(remaining, key=lambda row: calculate_distance(current, (row['Latitude'], row['Longitude'])))
        visited.append(next_point)
        current = (next_point['Latitude'], next_point['Longitude'])
        remaining.remove(next_point)

    return visited

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.lower()
        required_cols = {"latitude", "longitude", "address"}
        if not required_cols.issubset(df.columns):
            st.error("Excel must contain: Latitude, Longitude, Address (any casing).")
            st.stop()

        # Clean and convert
        df = df.rename(columns={"latitude": "Latitude", "longitude": "Longitude", "address": "Address"})
        df = df.dropna(subset=["Latitude", "Longitude", "Address"])

        locations = df.to_dict(orient="records")

        if use_user_location and user_lat != 0.0 and user_lon != 0.0:
            start_point = (user_lat, user_lon)
        else:
            start_point = (locations[0]["Latitude"], locations[0]["Longitude"])

        ordered = find_greedy_route(start_point, locations.copy())

        total_distance = 0.0
        route_coords = []
        display_data = []

        current_point = start_point
        for loc in ordered:
            site_coord = (loc["Latitude"], loc["Longitude"])
            distance = calculate_distance(current_point, site_coord)
            total_distance += distance
            route_coords.append(site_coord)
            display_data.append({
                "Address": loc["Address"],
                "Latitude": loc["Latitude"],
                "Longitude": loc["Longitude"],
                "Distance from Previous (km)": round(distance, 2)
            })
            current_point = site_coord

        # Display info
        st.success(f"🛣️ Total Travel Distance: {round(total_distance, 2)} km")

        st.subheader("📌 Locations in Visit Order")
        st.dataframe(pd.DataFrame(display_data))

        # Show Map
        m = folium.Map(location=route_coords[0], zoom_start=10, tiles="CartoDB positron")

        for i, coord in enumerate(route_coords):
            folium.Marker(
                coord,
                popup=f"Stop {i+1}",
                tooltip=ordered[i]["Address"],
                icon=folium.Icon(color="blue" if i > 0 else "green")
            ).add_to(m)

        folium.PolyLine(route_coords, color="red", weight=3).add_to(m)

        st.subheader("🗺️ Visit Route Map")
        st_folium(m, width=1000, height=600)

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
