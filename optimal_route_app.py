import streamlit as st
import pandas as pd
import openrouteservice
from openrouteservice import convert
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from itertools import permutations
from io import BytesIO
from fpdf import FPDF

# Load ORS API key from secrets
API_KEY = st.secrets["ORS_API_KEY"]
client = openrouteservice.Client(key=API_KEY)

# --------------------- PDF Creation --------------------- #
def create_pdf_itinerary(locations, distances, durations):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Optimized Site Visit Itinerary", ln=True, align='C')
    pdf.ln(10)

    for i, loc in enumerate(locations):
        pdf.cell(200, 10, txt=f"{i+1}. {loc}", ln=True)
        if i < len(distances):
            pdf.cell(200, 10, txt=f"    → {distances[i]} km, approx. {durations[i]} mins", ln=True)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# --------------------- TSP Solver --------------------- #
def solve_tsp(coords, start_index):
    indices = list(range(len(coords)))
    best_order = []
    min_distance = float('inf')

    for perm in permutations(indices[1:]):
        order = [start_index] + list(perm)
        total_distance = 0
        for i in range(len(order) - 1):
            res = client.directions(
                coordinates=[coords[order[i]], coords[order[i+1]]],
                profile='driving-car',
                format='geojson'
            )
            total_distance += res['features'][0]['properties']['summary']['distance']
        if total_distance < min_distance:
            min_distance = total_distance
            best_order = order

    return best_order

# --------------------- Map Display --------------------- #
def display_map(coords, addresses):
    m = folium.Map(location=coords[0], zoom_start=10)
    marker_cluster = MarkerCluster().add_to(m)

    for i, (coord, addr) in enumerate(zip(coords, addresses)):
        folium.Marker(location=coord, popup=f"{i+1}. {addr}").add_to(marker_cluster)

    folium.PolyLine(coords, color='blue', weight=2.5).add_to(m)
    st_folium(m, width=700, height=500)

# --------------------- Streamlit App --------------------- #
st.set_page_config(page_title="Optimal Route Planner", layout="centered")
st.title("🗺️ Optimal Site Visit Route Planner")

uploaded_file = st.file_uploader("Upload Excel file (must contain columns: address, latitude, longitude)", type=["xlsx", "csv"])
start_lat = st.text_input("Optional Start Latitude (e.g. 6.5244)")
start_lon = st.text_input("Optional Start Longitude (e.g. 3.3792)")

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith("xlsx") else pd.read_csv(uploaded_file)
        st.success("File uploaded and read successfully.")

        if not all(col in df.columns for col in ["address", "latitude", "longitude"]):
            st.error("The file must contain 'address', 'latitude', and 'longitude' columns.")
        else:
            coords = list(zip(df['longitude'], df['latitude']))
            addresses = df['address'].tolist()

            if start_lat and start_lon:
                try:
                    user_coord = (float(start_lon), float(start_lat))
                    coords.insert(0, user_coord)
                    addresses.insert(0, "Start Location (User)")
                    start_index = 0
                except:
                    st.warning("Invalid latitude/longitude input. Ignoring start point.")
                    start_index = 0
            else:
                start_index = 0

            st.info("Calculating optimal route...")
            order = solve_tsp(coords, start_index)
            ordered_coords = [coords[i] for i in order]
            ordered_addresses = [addresses[i] for i in order]

            # Distances and durations
            ordered_distances_km = []
            ordered_times_min = []
            total_km = 0
            total_min = 0

            for i in range(len(order) - 1):
                res = client.directions(
                    coordinates=[ordered_coords[i], ordered_coords[i+1]],
                    profile='driving-car',
                    format='geojson'
                )
                summary = res['features'][0]['properties']['summary']
                distance_km = round(summary['distance'] / 1000, 2)
                duration_min = round(summary['duration'] / 60, 1)

                ordered_distances_km.append(distance_km)
                ordered_times_min.append(duration_min)

                total_km += distance_km
                total_min += duration_min

            st.subheader("🚦 Optimal Visit Order")
            for i, addr in enumerate(ordered_addresses):
                st.markdown(f"**{i+1}. {addr}**")
                if i < len(ordered_distances_km):
                    st.caption(f"→ {ordered_distances_km[i]} km, approx. {ordered_times_min[i]} mins")

            st.success(f"✅ Total Distance: {total_km} km, Estimated Time: {total_min} mins")

            # PDF & CSV
            pdf_buffer = create_pdf_itinerary(ordered_addresses, ordered_distances_km, ordered_times_min)
            csv_df = pd.DataFrame({
                "Order": list(range(1, len(ordered_addresses)+1)),
                "Address": ordered_addresses,
                "Distance to Next (km)": ordered_distances_km + [""],
                "Duration to Next (min)": ordered_times_min + [""],
            })

            st.download_button("📄 Download PDF Itinerary", data=pdf_buffer, file_name="route_itinerary.pdf")
            st.download_button("📑 Download CSV Itinerary", data=csv_df.to_csv(index=False), file_name="route_itinerary.csv")

            # Map last
            st.subheader("🗺️ Route Map")
            display_map(ordered_coords, ordered_addresses)

    except Exception as e:
        st.error(f"Error processing file: {e}")
