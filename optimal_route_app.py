import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import openrouteservice
from openrouteservice import distance_matrix
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from fpdf import FPDF
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Optimal Route Planner", layout="wide")

# Load ORS API Key from Streamlit secrets
API_KEY = st.secrets["ORS_API_KEY"]
ors_client = openrouteservice.Client(key=API_KEY)

@st.cache_data
def create_distance_matrix(locations):
    try:
        coords = [(lon, lat) for lat, lon in locations]  # ORS expects (lon, lat)
        matrix = ors_client.distance_matrix(locations=coords, metrics=["distance"], units="km")
        distances = matrix['distances']
        return distances
    except Exception as e:
        st.error(f"Error computing distance matrix: {e}")
        return None

def solve_tsp_ortools(distances):
    size = len(distances)
    if size <= 1:
        return None, 0

    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        return int(distances[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)] * 1000)  # in meters

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.time_limit.seconds = 10
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        index = routing.Start(0)
        route = []
        route_distance = 0
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, 0)
        route.append(manager.IndexToNode(index))
        return route, route_distance / 1000  # back to km
    return None, 0

def create_pdf_itinerary(addresses, total_km):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Visit Order Itinerary", ln=True)

    pdf.set_font("Arial", "", 12)
    for i, address in enumerate(addresses):
        pdf.cell(0, 10, f"{i + 1}. {address}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "I", 11)
    pdf.cell(0, 10, f"Total Distance: {total_km:.2f} km", ln=True)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# --- STREAMLIT UI ---
st.title("🚗 Optimal Site Visit Route Planner")
st.write("Upload an Excel file with `address`, `latitude`, and `longitude` columns.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.lower()
    required_columns = {"latitude", "longitude", "address"}

    if not required_columns.issubset(df.columns):
        st.error("Excel file must contain: latitude, longitude, and address columns.")
    else:
        st.subheader("📍 Enter Your Starting Location")
        user_lat = st.number_input("Your Latitude", format="%.6f")
        user_lon = st.number_input("Your Longitude", format="%.6f")

        if user_lat and user_lon:
            user_location = (user_lat, user_lon)

            df["Distance_from_You_km"] = df.apply(
                lambda row: geodesic(user_location, (row["latitude"], row["longitude"])).km, axis=1
            )
            df_sorted = df.sort_values("Distance_from_You_km")

            st.subheader("📌 Locations Sorted by Proximity to You")
            st.dataframe(df_sorted[["address", "Distance_from_You_km"]].style.format({"Distance_from_You_km": "{:.2f} km"}))

            # Prepare coordinates
            locations = [user_location] + list(zip(df_sorted["latitude"], df_sorted["longitude"]))
            addresses = ["Your Location"] + df_sorted["address"].tolist()

            st.subheader("📏 Distance Matrix")
            dist_matrix = create_distance_matrix(locations)
            if dist_matrix:
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
                        st.write(f"{i + 1}. {addr}")

                    export_df = pd.DataFrame({
                        "Order": list(range(1, len(order)+1)),
                        "Address": ordered_addresses,
                        "Latitude": [coord[0] for coord in ordered_coords],
                        "Longitude": [coord[1] for coord in ordered_coords]
                    })

                    csv = export_df.to_csv(index=False).encode()
                    st.download_button("📥 Download CSV Itinerary", csv, file_name="visit_order.csv")

                    pdf = create_pdf_itinerary(ordered_addresses, total_distance)
                    st.download_button("📄 Download PDF Itinerary", pdf, file_name="visit_order.pdf")

                    st.subheader("🗺️ Route Map")
                    route_map = folium.Map(location=user_location, zoom_start=11)
                    for i, coord in enumerate(ordered_coords):
                        folium.Marker(
                            location=coord,
                            popup=f"{i+1}. {ordered_addresses[i]}",
                            icon=folium.Icon(color="blue", icon="info-sign")
                        ).add_to(route_map)
                    folium.PolyLine(locations=ordered_coords, color="red", weight=3, opacity=0.8).add_to(route_map)
                    st_folium(route_map, width=900)
