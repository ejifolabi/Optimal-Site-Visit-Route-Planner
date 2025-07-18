import streamlit as st
import pandas as pd
import numpy as np
import openrouteservice
from openrouteservice import distance_matrix
from io import BytesIO
from fpdf import FPDF
import math
import base64

# ORS API client
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjllNTVjYmRjZjRjMzQ2NTE5NzY1ZjhkZGQzYjcwMDYwIiwiaCI6Im11cm11cjY0In0="
client = openrouteservice.Client(key=ORS_API_KEY)

st.set_page_config(page_title="Optimal Site Visit Planner", layout="wide")

st.title("📍 Optimal Site Visit Route Planner")
st.markdown("""
Upload an Excel file with columns: `Latitude`, `Longitude`, and `Address` to determine the most cost-effective site visit route using real road distances and travel time.
""")

uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])

# Optional user start point
with st.expander("📍 Optional: Add Your Starting Location"):
    start_lat = st.text_input("Latitude")
    start_lon = st.text_input("Longitude")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_distance_matrix(coords):
    res = client.distance_matrix(
        locations=coords,
        profile='driving-car',
        metrics=['distance', 'duration'],
        resolve_locations=False
    )
    return np.array(res['distances']), np.array(res['durations'])

def nearest_neighbor(dist_matrix, start_idx):
    n = len(dist_matrix)
    visited = [False]*n
    order = [start_idx]
    visited[start_idx] = True
    for _ in range(n-1):
        last = order[-1]
        next_idx = np.argmin([dist_matrix[last][j] if not visited[j] else float('inf') for j in range(n)])
        order.append(next_idx)
        visited[next_idx] = True
    return order

def create_pdf_itinerary(addresses, distances_km, times_min):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="📍 Optimal Site Visit Itinerary", ln=1, align="C")
    pdf.ln(5)
    total_distance = 0
    total_time = 0
    for i, (addr, dist, dur) in enumerate(zip(addresses, distances_km, times_min)):
        pdf.multi_cell(0, 10, txt=f"{i+1}. {addr}\nDistance from last stop: {dist:.2f} km | Time: {dur:.1f} mins")
        total_distance += dist
        total_time += dur
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Total Distance: {total_distance:.2f} km | Total Time: {total_time:.1f} mins", ln=1)
    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if {'Latitude', 'Longitude', 'Address'}.issubset(df.columns):
        st.success("✅ File loaded successfully.")

        coordinates = list(zip(df['Longitude'], df['Latitude']))
        addresses = df['Address'].tolist()

        # Handle optional start location
        if start_lat and start_lon:
            try:
                user_coord = (float(start_lon), float(start_lat))
                coordinates.insert(0, user_coord)
                addresses.insert(0, "📍 User Starting Location")
                st.info("Using custom user start location.")
            except:
                st.warning("Invalid coordinates. Skipping custom start.")
        
        # Calculate real road distance and time matrix
        dist_matrix, time_matrix = get_distance_matrix(coordinates)

        # Determine start and farthest end
        if start_lat and start_lon:
            start_idx = 0
        else:
            # Find closest point as starting location
            origin = (coordinates[0][1], coordinates[0][0])
            dists = [haversine(origin[0], origin[1], lat, lon) for lon, lat in coordinates]
            start_idx = int(np.argmin(dists))

        # Get order using greedy NN
        visit_order = nearest_neighbor(dist_matrix, start_idx)
        ordered_addresses = [addresses[i] for i in visit_order]

        # Ordered distances from last stop
        ordered_distances_km = []
        ordered_times_min = []
        for i in range(len(visit_order)-1):
            a, b = visit_order[i], visit_order[i+1]
            ordered_distances_km.append(dist_matrix[a][b]/1000)
            ordered_times_min.append(time_matrix[a][b]/60)
        ordered_distances_km.insert(0, 0)
        ordered_times_min.insert(0, 0)

        # Show itinerary
        itinerary_df = pd.DataFrame({
            "Visit Order": range(1, len(ordered_addresses)+1),
            "Address": ordered_addresses,
            "Distance from Previous (km)": ordered_distances_km,
            "Travel Time (min)": ordered_times_min
        })

        st.subheader("📋 Optimized Visit Itinerary")
        st.dataframe(itinerary_df, use_container_width=True)

        # Download CSV
        csv = itinerary_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv, file_name="site_visit_itinerary.csv", mime='text/csv')

        # Download PDF
        pdf_buffer = create_pdf_itinerary(ordered_addresses, ordered_distances_km, ordered_times_min)
        st.download_button("📥 Download PDF", data=pdf_buffer, file_name="site_visit_itinerary.pdf", mime="application/pdf")

    else:
        st.error("❌ The Excel file must contain 'Latitude', 'Longitude', and 'Address' columns.")
