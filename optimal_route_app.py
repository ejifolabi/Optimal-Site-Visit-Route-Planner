import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(page_title="Optimal Site Visit Route Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")

st.markdown("Upload an Excel file with columns: **Latitude, Longitude, Address**. Optionally include **S/N**.")

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
            st.error("Excel must contain at least: Latitude, Longitude, Address (case-insensitive).")
            st.stop()

        has_sn = "s/n" in df.columns

        # Rename for consistent capitalization
        rename_dict = {
            "latitude": "Latitude",
            "longitude": "Longitude",
            "address": "Address"
        }
        if has_sn:
            rename_dict["s/n"] = "S/N"
        df = df.rename(columns=rename_dict)

        # Drop missing
        drop_cols = ["Latitude", "Longitude", "Address"]
        if has_sn:
            drop_cols.append("S/N")
        df = df.dropna(subset=drop_cols)

        # Convert to dict for route finding
        locations = df.to_dict(orient="records")

        # Starting point
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

            row = {
                "Latitude": loc["Latitude"],
                "Longitude": loc["Longitude"],
                "Address": loc["Address"],
                "Distance from Previous (km)": round(distance, 2)
            }
            if has_sn:
                row = {"S/N": loc["S/N"], **row}  # Ensure S/N is the first column

            display_data.append(row)
            current_point = site_coord

        # Display summary
        st.success(f"🛣️ Total Travel Distance: {round(total_distance, 2)} km")

        # Table
        st.subheader("📌 Locations in Visit Order")
        st.dataframe(pd.DataFrame(display_data))

        # Map
        m = folium.Map(location=route_coords[0], zoom_start=10, tiles="CartoDB positron")

        for i, coord in enumerate(route_coords):
            marker_label = str(ordered[i]["S/N"]) if has_sn else ordered[i]["Address"]
            folium.Marker(
                coord,
                popup=f"Stop {i+1}",
                tooltip=marker_label,
                icon=folium.Icon(color="blue" if i > 0 else "green")
            ).add_to(m)

        folium.PolyLine(route_coords, color="red", weight=3).add_to(m)

        st.subheader("🗺️ Visit Route Map")
        st_folium(m, width=1000, height=600)

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
