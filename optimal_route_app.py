import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium, folium_static  # Fallback added

st.set_page_config(page_title="Optimal Site Visit Route Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")

st.markdown("Upload Excel: **Latitude, Longitude, Address** (case-insensitive). Optional **S/N**.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

with st.expander("📍 Optional: Your Current Location"):
    user_lat = st.number_input("Latitude", value=0.0, format="%.6f")
    user_lon = st.number_input("Longitude", value=0.0, format="%.6f")
    use_user_location = st.checkbox("Use as starting point", value=False)

@st.cache_data
def calculate_distance(coord1, coord2):
    return geodesic(coord1, coord2).km

def find_greedy_route(start, points_df):
    """Fixed: Use indices to avoid mutation/hash errors."""
    points = points_df.copy()
    visited_indices = []
    current = start
    remaining_indices = list(range(len(points)))

    while remaining_indices:
        distances = [calculate_distance(current, (points.iloc[i]['Latitude'], points.iloc[i]['Longitude'])) for i in remaining_indices]
        next_idx = remaining_indices[distances.index(min(distances))]
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
            st.error(f"Missing columns: {', '.join(missing)}")
            st.stop()

        # Standardize names
        df = df.rename(columns={
            "latitude": "Latitude", "longitude": "Longitude", "address": "Address",
            "s/n": "S/N"
        })

        # Validate coords (Nigeria/Kebbi focus)
        df = df[(df['Latitude'].between(4, 15)) & (df['Longitude'].between(2, 15))]
        if df.empty:
            st.error("No valid Nigeria-range coords found.")
            st.stop()

        df = df.dropna(subset=["Latitude", "Longitude", "Address"])

        if len(df) < 1:
            st.error("No valid sites after cleaning.")
            st.stop()

        has_sn = "S/N" in df.columns
        locations = df

        # Start point
        if use_user_location and user_lat != 0.0 and user_lon != 0.0:
            start_point = (user_lat, user_lon)
            start_name = "Your Location"
        else:
            start_point = (df.iloc[0]['Latitude'], df.iloc[0]['Longitude'])
            start_name = df.iloc[0]['Address']

        ordered_df = find_greedy_route(start_point, locations)

        # Build route with distances
        total_distance = 0.0
        route_coords = [start_point]
        display_data = []
        current_point = start_point

        # Starting point row
        row0 = {"Latitude": start_point[0], "Longitude": start_point[1], "Address": start_name, "Distance from Previous (km)": 0.0}
        if has_sn: row0["S/N"] = ""
        display_data.append(row0)

        for _, loc in ordered_df.iterrows():
            site_coord = (loc["Latitude"], loc["Longitude"])
            distance = calculate_distance(current_point, site_coord)
            total_distance += distance
            route_coords.append(site_coord)

            row = {"Latitude": loc["Latitude"], "Longitude": loc["Longitude"], "Address": loc["Address"], "Distance from Previous (km)": round(distance, 2)}
            if has_sn: row["S/N"] = loc["S/N"]
            display_data.append(row)
            current_point = site_coord

        st.success(f"🛣️ Total Distance: {round(total_distance, 2)} km ({len(ordered_df)} sites)")

        st.subheader("📌 Visit Order")
        st.dataframe(pd.DataFrame(display_data))

        # Map with fallback
        m = folium.Map(location=route_coords[0], zoom_start=10, tiles="CartoDB positron")
        colors = ["green"] + ["blue"] * (len(route_coords)-1)

        for i, coord in enumerate(route_coords):
            label = display_data[i].get("S/N", display_data[i]["Address"][:20])
            folium.Marker(
                coord, popup=f"Stop {i}", tooltip=label,
                icon=folium.Icon(color=colors[i])
            ).add_to(m)

        folium.PolyLine(route_coords, color="red", weight=4, opacity=0.8).add_to(m)

        st.subheader("🗺️ Route Map")
        try:
            st_folium(m, width=1000, height=600, returned_objects=[])
        except:
            st.warning("st_folium failed—using static fallback.")
            folium_static(m, width=1000, height=600)

    except Exception as e:
        st.error(f"Error: {str(e)}. Check file format/coords.")
        st.exception(e)
