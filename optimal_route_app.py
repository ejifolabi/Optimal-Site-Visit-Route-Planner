import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from openrouteservice import Client
from openrouteservice.distance_matrix import distance_matrix
from scipy.spatial.distance import cdist
import numpy as np
from fpdf import FPDF
from io import BytesIO
import itertools

# Title
st.set_page_config(page_title="Optimal Site Visit Route Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")
st.markdown("This app calculates the optimal route to visit multiple locations based on real road distances using OpenRouteService API.")

# Load ORS API Key
API_KEY = st.secrets["ORS_API_KEY"]
client = Client(key=API_KEY)

# Upload Excel file
uploaded_file = st.file_uploader("Upload an Excel file with latitude, longitude, and address", type=["xlsx"])
if not uploaded_file:
    st.info("⬆️ Upload a file to begin")
    st.stop()

# Read Excel
try:
    df = pd.read_excel(uploaded_file)
    required_cols = {"latitude", "longitude", "address"}
    if not required_cols.issubset(df.columns):
        st.error("Excel must contain 'latitude', 'longitude', and 'address' columns.")
        st.stop()
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

# Limit number of addresses
if len(df) > 20:
    st.warning("Only the first 20 addresses will be used to optimize the route for performance reasons.")
    df = df.iloc[:20]

coordinates = df[["longitude", "latitude"]].values.tolist()
addresses = df["address"].tolist()

# Optional user start location
user_lat = st.text_input("Enter your starting latitude (optional)")
user_lon = st.text_input("Enter your starting longitude (optional)")

if user_lat and user_lon:
    try:
        start_point = [float(user_lon), float(user_lat)]
        coordinates.insert(0, start_point)
        addresses.insert(0, "Start Location")
    except:
        st.warning("Invalid start coordinates. Using first address as start point.")

@st.cache_data(show_spinner=False)
def get_distance_matrix(coords):
    matrix = distance_matrix(
        client,
        locations=coords,
        profile='driving-car',
        metrics=["distance", "duration"],
        units="km"
    )
    return matrix

@st.cache_data(show_spinner=False)
def solve_tsp(distances):
    n = len(distances)
    all_indices = list(range(n))
    min_distance = float("inf")
    best_order = []

    for perm in itertools.permutations(all_indices[1:]):
        current_order = [0] + list(perm)
        dist = sum(distances[current_order[i]][current_order[i+1]] for i in range(n-1))
        if dist < min_distance:
            min_distance = dist
            best_order = current_order

    return best_order

@st.cache_data(show_spinner=False)
def create_pdf_itinerary(addresses, distances, durations):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Optimal Route Itinerary", ln=True, align="C")
    pdf.ln(10)
    for i, (addr, dist, dur) in enumerate(zip(addresses, distances, durations)):
        pdf.multi_cell(0, 10, f"{i+1}. {addr}\n   Distance: {dist:.2f} km | Time: {dur:.2f} min")
        pdf.ln(1)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# Spinner for API and computation
with st.spinner("Calculating optimal route..."):
    matrix = get_distance_matrix(coordinates)
    distance_matrix_km = np.array(matrix['distances'])
    duration_matrix_min = np.array(matrix['durations'])

    order = solve_tsp(distance_matrix_km)
    ordered_coords = [coordinates[i] for i in order]
    ordered_addresses = [addresses[i] for i in order]
    ordered_distances_km = [distance_matrix_km[order[i]][order[i+1]] for i in range(len(order)-1)]
    ordered_times_min = [duration_matrix_min[order[i]][order[i+1]] for i in range(len(order)-1)]

# Show ordered itinerary
st.subheader("🚗 Optimized Visit Order")
for i, (addr, dist, dur) in enumerate(zip(ordered_addresses[1:], ordered_distances_km, ordered_times_min), start=1):
    st.markdown(f"**{i}. {addr}**")
    st.caption(f"Distance: {dist:.2f} km | Estimated time: {dur:.2f} minutes")

# Download itinerary as PDF
pdf_buffer = create_pdf_itinerary(ordered_addresses, ordered_distances_km, ordered_times_min)
st.download_button("📄 Download Itinerary as PDF", data=pdf_buffer, file_name="itinerary.pdf")

# Display map only after everything
st.subheader("🗺️ Route Map")
map_center = ordered_coords[0][::-1]
map_route = folium.Map(location=map_center, zoom_start=10)
for i, coord in enumerate(ordered_coords):
    folium.Marker(
        location=coord[::-1],
        popup=f"{i+1}. {ordered_addresses[i]}",
        icon=folium.Icon(color='blue', icon='info-sign')
    ).add_to(map_route)

folium.PolyLine([coord[::-1] for coord in ordered_coords], color="red", weight=2.5).add_to(map_route)
st_folium(map_route, width=1000, height=500)
