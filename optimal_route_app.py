import streamlit as st
import pandas as pd
import numpy as np
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from io import BytesIO
import base64
from fpdf import FPDF

st.set_page_config(page_title="Optimal Site Visit Planner", layout="wide")

st.title("📍 Optimal Site Visit Route Planner")
st.markdown("""
Upload an Excel file with site information (latitude, longitude, address), and this app will:
- Compute distances between all sites.
- Find the optimal visit route using Google OR-Tools.
- Display an interactive map and export itinerary.
""")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# ------------------------------
def create_distance_matrix(locations):
    n = len(locations)
    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                dist_matrix[i][j] = geodesic(locations[i], locations[j]).km
    return dist_matrix.tolist()

def solve_tsp_ortools(distance_matrix):
    n = len(distance_matrix)

    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        return int(distance_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)] * 1000)

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        return None, None

    index = routing.Start(0)
    route = []
    total_distance = 0
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        route.append(node)
        previous_index = index
        index = solution.Value(routing.NextVar(index))
        total_distance += routing.GetArcCostForVehicle(previous_index, index, 0)
    route.append(manager.IndexToNode(index))

    return route, total_distance / 1000  # convert back to km

# ------------------------------
def create_pdf_itinerary(ordered_addresses, total_distance):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Optimal Visit Itinerary", ln=1, align='C')
    pdf.ln(5)
    for i, addr in enumerate(ordered_addresses):
        pdf.cell(0, 10, txt=f"{i+1}. {addr}", ln=1)
    pdf.ln(5)
    pdf.cell(0, 10, txt=f"Total Distance: {total_distance:.2f} km", ln=1)
    
    # Fix: return PDF as bytes via 'S' (string) output
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    pdf_output = BytesIO(pdf_bytes)
    pdf_output.seek(0)
    return pdf_output

# ------------------------------
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.lower()
    required_columns = {"latitude", "longitude", "address"}

    if not required_columns.issubset(df.columns):
        st.error("Excel must contain columns: latitude, longitude, address")
    else:
        locations = list(zip(df['latitude'], df['longitude']))
        addresses = df['address'].tolist()

        st.subheader("📏 Distance Matrix")
        dist_matrix = create_distance_matrix(locations)
        dist_df = pd.DataFrame(dist_matrix, columns=addresses, index=addresses)
        st.dataframe(dist_df.style.format("{:.2f} km"))

        st.subheader("🧭 Optimal Visit Order (Google OR-Tools)")
        with st.spinner("Optimizing route..."):
            order, total_distance = solve_tsp_ortools(dist_matrix)
            if order is None:
                st.error("Could not solve TSP. Try fewer locations.")
            else:
                ordered_addresses = [addresses[i] for i in order]
                ordered_coords = [locations[i] for i in order]

                st.success(f"✅ Total Route Distance: {total_distance:.2f} km")

                st.markdown("### Suggested Visit Order:")
                for i, addr in enumerate(ordered_addresses):
                    st.write(f"{i+1}. {addr}")

                # Export itinerary
                export_df = pd.DataFrame({
                    "Order": list(range(1, len(order)+1)),
                    "Address": ordered_addresses,
                    "Latitude": [loc[0] for loc in ordered_coords],
                    "Longitude": [loc[1] for loc in ordered_coords]
                })

                csv = export_df.to_csv(index=False).encode()
                st.download_button("📥 Download CSV Itinerary", csv, file_name="visit_order.csv", mime="text/csv")

                pdf = create_pdf_itinerary(ordered_addresses, total_distance)
                st.download_button("📄 Download PDF Itinerary", pdf, file_name="visit_order.pdf")

                # Map
                st.subheader("🗺️ Route Map")
                map = folium.Map(location=locations[0], zoom_start=11)
                for i, idx in enumerate(order):
                    folium.Marker(location=locations[idx], popup=f"{i+1}. {addresses[idx]}",
                                  icon=folium.Icon(color="blue")).add_to(map)

                folium.PolyLine(locations=ordered_coords, color="red", weight=3, opacity=0.8).add_to(map)
                st_folium(map, width=900)
