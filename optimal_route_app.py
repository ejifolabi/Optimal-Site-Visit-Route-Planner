import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from folium.plugins import BeautifyIcon

# =========================
# APP CONFIG
# =========================
st.set_page_config(page_title="🚀 Nigerian Route Optimizer", layout="wide")
st.title("🇳🇬 Fast Route Optimizer (10x Faster with OR-Tools)")

uploaded_file = st.file_uploader("📂 Upload your Excel or CSV file", type=["xlsx", "csv"])

# =========================
# FILE LOADER
# =========================
def load_file(file):
    name = file.name.lower()

    # Read raw file
    if name.endswith(".csv"):
        raw = pd.read_csv(file, header=None)
    else:
        raw = pd.read_excel(file, header=None)

    # Detect header
    header_row = None
    for i, row in raw.iterrows():
        r = [str(x).lower() for x in row.values if pd.notna(x)]
        if any("lat" in x for x in r) and any("lon" in x or "lng" in x for x in r):
            header_row = i
            break

    if header_row is None:
        st.error("❌ Could not detect header row (Latitude/Longitude missing)")
        st.stop()

    # Reload correctly with header
    if name.endswith(".csv"):
        df = pd.read_csv(file, header=header_row)
    else:
        df = pd.read_excel(file, header=header_row)

    return df


# =========================
# CLEAN & PREPARE DATA
# =========================
def clean(df):
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains("unnamed")]

    mapping = {}
    for c in df.columns:
        if "lat" in c:
            mapping[c] = "Latitude"
        elif "lon" in c or "lng" in c:
            mapping[c] = "Longitude"
        elif "address" in c or "site" in c or "name" in c:
            mapping[c] = "Address"
        elif "s/n" in c or c in ["sn", "sno", "no"]:
            mapping[c] = "S/N"

    df = df.rename(columns=mapping)
    df = df.loc[:, ~df.columns.duplicated()]

    required = ["Latitude", "Longitude", "Address"]
    for r in required:
        if r not in df.columns:
            st.error(f"❌ Missing required column: {r}")
            st.stop()

    return df.dropna(subset=required)


# =========================
# DISTANCE MATRIX
# =========================
@st.cache_data(show_spinner=False)
def create_distance_matrix(locations):
    size = len(locations)
    matrix = [[0]*size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i != j:
                dist = geodesic(locations[i], locations[j]).km
                matrix[i][j] = int(dist * 1000)  # meters
    return matrix


# =========================
# TSP SOLVER
# =========================
def solve_tsp(distance_matrix):
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        st.error("❌ Route optimization failed")
        st.stop()

    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    return route


# =========================
# OSRM ROUTE VISUALIZATION
# =========================
@st.cache_data(show_spinner=False)
def get_road_path(start, end):
    # OSRM expects: longitude,latitude
    start_lng, start_lat = start[1], start[0]
    end_lng, end_lat = end[1], end[0]

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lng},{start_lat};{end_lng},{end_lat}"
        f"?overview=full&geometries=geojson"
    )

    try:
        r = requests.get(url, timeout=10).json()
        if "routes" in r and r["routes"]:
            coords = r["routes"][0]["geometry"]["coordinates"]
            return [[lat, lon] for lon, lat in coords]
    except Exception as e:
        print("OSRM error:", e)

    return None


# =========================
# MAIN LOGIC
# =========================
if uploaded_file:
    df = load_file(uploaded_file)
    df = clean(df)

    locations = list(zip(df["Latitude"], df["Longitude"]))
    names = df["Address"].astype(str).tolist()

    st.success(f"✅ {len(locations)} locations loaded successfully")

    with st.spinner("⚡ Computing optimal route (Using OR-Tools)..."):
        dist_matrix = create_distance_matrix(locations)
        route_idx = solve_tsp(dist_matrix)

    optimized_locations = [locations[i] for i in route_idx]
    optimized_names = [names[i] for i in route_idx]

    # =========================
    # MAP DISPLAY
    # =========================
    st.subheader("🗺️ Optimized Route Map")

    start_loc = optimized_locations[0]
    m = folium.Map(location=start_loc, zoom_start=10, tiles="CartoDB positron")

    # Numbered markers with icons
    for i, loc in enumerate(optimized_locations):
        folium.Marker(
            loc,
            tooltip=f"{i+1}. {optimized_names[i]}",
            icon=BeautifyIcon(
                number=i + 1,
                border_color="#000000",
                text_color="white",
                background_color="#007bff",
                inner_icon_style="margin-top:-1px;",
            ),
        ).add_to(m)

    # Draw road paths
    for i in range(len(optimized_locations) - 1):
        road = get_road_path(optimized_locations[i], optimized_locations[i + 1])
        if road:
            folium.PolyLine(road, color="blue", weight=5, opacity=0.8).add_to(m)

    st_folium(m, width=1200, height=600)

    # =========================
    # RESULT TABLE
    # =========================
    st.subheader("📋 Optimized Route Order")

    result = pd.DataFrame({
        "Step": range(1, len(optimized_names) + 1),
        "Location Name": optimized_names,
        "Latitude": [x[0] for x in optimized_locations],
        "Longitude": [x[1] for x in optimized_locations]
    })

    st.dataframe(result, use_container_width=True)

    st.download_button(
        "⬇️ Download Optimized Route CSV",
        result.to_csv(index=False),
        "optimized_route.csv",
        "text/csv"
    )
