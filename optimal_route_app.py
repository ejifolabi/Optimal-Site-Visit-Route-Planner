import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import openrouteservice
from openrouteservice import convert
import io
from fpdf import FPDF
import polyline

st.set_page_config(page_title="Optimal Site Visit Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")

# --- Input Section ---
st.markdown("Upload an Excel file with columns: Address, Latitude, Longitude")
uploaded_file = st.file_uploader("Choose an Excel file", type=[".xlsx"])

# --- ORS API Key ---
API_KEY = st.secrets["ORS_API_KEY"]
client = openrouteservice.Client(key=API_KEY)

# --- Helper to Generate PDF ---
def create_pdf_itinerary(addresses, distances_km, durations_min):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Optimal Visit Itinerary", ln=1, align="C")

    for i, (addr, dist, dur) in enumerate(zip(addresses, distances_km, durations_min)):
        pdf.cell(200, 10, txt=f"{i+1}. {addr}", ln=1)
        pdf.cell(200, 10, txt=f"   Distance: {dist:.2f} km | Duration: {dur:.1f} min", ln=1)

    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# --- Optimization Section ---
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if not {'Latitude', 'Longitude', 'Address'}.issubset(df.columns):
        st.error("The Excel file must contain 'Address', 'Latitude', and 'Longitude' columns.")
    else:
        locations = df[['Longitude', 'Latitude']].values.tolist()
        addresses = df['Address'].tolist()

        # --- ORS Optimization API ---
        jobs = [
            {"id": i+1, "location": coord} for i, coord in enumerate(locations[1:])
        ]

        vehicle = {
            "id": 1,
            "start": locations[0],
            "end": locations[0],
        }

        try:
            res = client.optimization(jobs=jobs, vehicles=[vehicle])
            route = res['routes'][0]['steps']
            ordered_indices = [0] + [step['job'] for step in route if 'job' in step]
            ordered_coords = [locations[0]] + [locations[i] for i in [j-1 for j in ordered_indices[1:]]]
            ordered_addresses = [addresses[0]] + [addresses[i] for i in [j-1 for j in ordered_indices[1:]]]

            # --- Get actual directions between ordered waypoints ---
            directions = client.directions(ordered_coords, profile='driving-car', format='geojson')
            segments = directions['features'][0]['properties']['segments']

            ordered_distances_km = [seg['distance']/1000 for seg in segments]
            ordered_times_min = [seg['duration']/60 for seg in segments]

            st.success("✅ Optimal Route Computed Successfully!")
            st.subheader("📋 Visit Order")

            for i, (addr, dist, dur) in enumerate(zip(ordered_addresses, ordered_distances_km, ordered_times_min)):
                st.markdown(f"**{i+1}. {addr}**  ")
                st.markdown(f"Distance: {dist:.2f} km | Duration: {dur:.1f} min")

            # --- Download Itinerary as PDF ---
            pdf_buffer = create_pdf_itinerary(ordered_addresses, ordered_distances_km, ordered_times_min)
            st.download_button("📄 Download Itinerary as PDF", data=pdf_buffer, file_name="itinerary.pdf")

            # --- Map Section (Last) ---
            st.subheader("🗺️ Route Map")
            m = folium.Map(location=locations[0][::-1], zoom_start=12)
            MarkerCluster().add_to(m)

            for idx, coord in enumerate(ordered_coords):
                folium.Marker(coord[::-1], tooltip=f"{idx+1}. {ordered_addresses[idx]}").add_to(m)

            folium.PolyLine(locations=[coord[::-1] for coord in ordered_coords], color="blue", weight=5).add_to(m)
            st_folium(m, width=1000, height=600)

        except Exception as e:
            st.error(f"❌ Failed to compute optimal route: {e}")
