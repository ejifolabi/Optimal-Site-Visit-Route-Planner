import streamlit as st
import pandas as pd
import openrouteservice
from openrouteservice import convert
import folium
from streamlit_folium import st_folium
from io import BytesIO
from fpdf import FPDF
from geopy.distance import geodesic

# ------------------------------
# CONFIGURATION
# ------------------------------
API_KEY = st.secrets["ORS_API_KEY"]  # Save your ORS key in Streamlit Secrets
client = openrouteservice.Client(key=API_KEY)

# ------------------------------
# PDF GENERATION
# ------------------------------
def create_pdf_itinerary(addresses, distances_km, durations_min):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Optimal Site Visit Itinerary", ln=True, align='C')
    pdf.ln(10)

    for i, addr in enumerate(addresses):
        text = f"{i+1}. {addr}"
        if i < len(distances_km):
            text += f"\n   Distance to next: {distances_km[i]:.2f} km, Time: {durations_min[i]:.2f} mins"
        pdf.multi_cell(0, 10, txt=text)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# ------------------------------
# DISTANCE & DURATION WITH ORS
# ------------------------------
def get_route_info(coords):
    route = client.directions(coords, profile='driving-car', format='geojson')
    summary = route['features'][0]['properties']['summary']
    distance_km = summary['distance'] / 1000
    duration_min = summary['duration'] / 60
    return distance_km, duration_min

# ------------------------------
# NEAREST POINT (GREEDY TSP)
# ------------------------------
def solve_tsp_greedy(coords):
    visited = [0]
    while len(visited) < len(coords):
        last = coords[visited[-1]]
        nearest = min(
            [(i, geodesic(last, coords[i]).km) for i in range(len(coords)) if i not in visited],
            key=lambda x: x[1]
        )[0]
        visited.append(nearest)
    return visited

# ------------------------------
# MAPPING FUNCTION
# ------------------------------
def show_map(addresses, lats, lons, distances_km=None, durations_min=None):
    start_lat, start_lon = lats[0], lons[0]
    m = folium.Map(location=[start_lat, start_lon], zoom_start=12)

    for i, (addr, lat, lon) in enumerate(zip(addresses, lats, lons)):
        popup_text = f"{i+1}. {addr}"
        if distances_km and durations_min and i < len(distances_km):
            popup_text += f"<br>Distance: {distances_km[i]:.2f} km<br>Time: {durations_min[i]:.2f} min"

        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color="green" if i == 0 else "blue", icon="info-sign")
        ).add_to(m)

    route_points = list(zip(lats, lons))
    folium.PolyLine(locations=route_points, color="red", weight=3).add_to(m)

    st_folium(m, width=700, height=500)

# ------------------------------
# MAIN APP
# ------------------------------
st.title("Optimal Site Visit Route Planner")
st.write("Upload an Excel file with columns: `Latitude`, `Longitude`, and `Address`")

user_lat = st.text_input("Enter your current Latitude (optional)")
user_lon = st.text_input("Enter your current Longitude (optional)")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if not all(col in df.columns for col in ['Latitude', 'Longitude', 'Address']):
        st.error("Excel must contain 'Latitude', 'Longitude', and 'Address' columns")
    else:
        latitudes = df['Latitude'].tolist()
        longitudes = df['Longitude'].tolist()
        addresses = df['Address'].tolist()

        if user_lat and user_lon:
            try:
                user_coord = (float(user_lat), float(user_lon))
                latitudes.insert(0, user_coord[0])
                longitudes.insert(0, user_coord[1])
                addresses.insert(0, "User Location")
            except:
                st.warning("Invalid coordinates. Skipping user location.")

        coords = list(zip(latitudes, longitudes))

        # Solve TSP Greedily
        order = solve_tsp_greedy(coords)

        ordered_coords = [coords[i] for i in order]
        ordered_addresses = [addresses[i] for i in order]
        ordered_latitudes = [latitudes[i] for i in order]
        ordered_longitudes = [longitudes[i] for i in order]

        ordered_distances_km = []
        ordered_times_min = []
        for i in range(len(ordered_coords) - 1):
            d_km, t_min = get_route_info([ordered_coords[i][::-1], ordered_coords[i+1][::-1]])
            ordered_distances_km.append(d_km)
            ordered_times_min.append(t_min)

        st.success("Optimal route calculated!")

        st.subheader("Map View")
        show_map(ordered_addresses, ordered_latitudes, ordered_longitudes, ordered_distances_km, ordered_times_min)

        st.subheader("Download PDF Itinerary")
        pdf_buffer = create_pdf_itinerary(ordered_addresses, ordered_distances_km, ordered_times_min)
        st.download_button(
            label="📄 Download Itinerary",
            data=pdf_buffer,
            file_name="itinerary.pdf",
            mime="application/pdf"
        )
