import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import openrouteservice
from openrouteservice import convert
from io import BytesIO
import pdfkit

st.set_page_config(page_title="Smart Site Visit Route", layout="wide")
st.title("📍 Smart Site Visit Route Planner")
st.markdown("Upload an Excel file with **Latitude, Longitude, Address** (not case-sensitive). You may optionally enter your start location.")

@st.cache_resource
def get_ors_client():
    return openrouteservice.Client(key=st.secrets["ORS_API_KEY"])

@st.cache_data
def clean_dataframe(file):
    df = pd.read_excel(file)
    df.columns = [c.lower().strip() for c in df.columns]
    df.rename(columns={"latitude": "lat", "longitude": "lon", "address": "address"}, inplace=True)
    return df[["lat", "lon", "address"]]

@st.cache_data
def get_sorted_by_closest(start_coords, df):
    distances = []
    for _, row in df.iterrows():
        coord = (row["lat"], row["lon"])
        dist = geodesic(start_coords, coord).km
        distances.append(dist)
    df["distance_km"] = distances
    return df.sort_values("distance_km")

@st.cache_data
def generate_route(client, coords):
    return client.directions(coords, profile='driving-car', format='geojson')

def plot_route_map(route, locations):
    start = locations[0][::-1]
    fmap = folium.Map(location=start, zoom_start=11, tiles="CartoDB positron")

    folium.Marker(start, tooltip="Start", icon=folium.Icon(color="green")).add_to(fmap)
    for i, loc in enumerate(locations[1:], 1):
        folium.Marker(loc[::-1], tooltip=f"Stop {i}", icon=folium.Icon(color="blue")).add_to(fmap)

    folium.GeoJson(route, name="route").add_to(fmap)
    return fmap

def generate_pdf(route_geojson, total_distance_km):
    html = f"""
    <html><body>
    <h1>Route Plan</h1>
    <p>Total Distance: {total_distance_km:.2f} km</p>
    <p>Route GeoJSON:</p>
    <pre>{route_geojson}</pre>
    </body></html>
    """
    pdf = pdfkit.from_string(html, False)
    return BytesIO(pdf)

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = clean_dataframe(uploaded_file)

    st.subheader("🔍 Optional: Enter Your Start Location")
    with st.form("start_form"):
        lat = st.text_input("Latitude", "")
        lon = st.text_input("Longitude", "")
        submit = st.form_submit_button("Set as Starting Point")

    if submit and lat and lon:
        try:
            start_coords = (float(lat), float(lon))
        except ValueError:
            st.error("Invalid coordinates. Please enter numeric values.")
            st.stop()
    else:
        start_coords = (df.iloc[0]["lat"], df.iloc[0]["lon"])

    sorted_df = get_sorted_by_closest(start_coords, df)
    st.subheader("📋 Sorted Locations (Closest First)")
    st.dataframe(sorted_df[["address", "lat", "lon", "distance_km"]], use_container_width=True)

    coords = [(row["lon"], row["lat"]) for _, row in sorted_df.iterrows()]
    client = get_ors_client()
    route_geojson = generate_route(client, coords)

    st.subheader("🗺️ Route Map")
    route_map = plot_route_map(route_geojson, coords)
    st_data = st_folium(route_map, width=1000, height=600)

    total_km = sorted_df["distance_km"].sum()
    st.write(f"**Total Estimated Travel Distance:** {total_km:.2f} km")

    if "pdf_ready" not in st.session_state:
        st.session_state["pdf_ready"] = False

    if st.button("⬇️ Prepare Route PDF"):
        st.session_state["pdf_ready"] = True

    if st.session_state["pdf_ready"]:
        pdf_file = generate_pdf(route_geojson, total_km)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_file.getvalue(),
            file_name="route_plan.pdf",
            mime="application/pdf"
        )
