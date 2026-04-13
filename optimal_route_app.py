import streamlit as st
import pandas as pd
import folium
import requests
import numpy as np
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from folium.plugins import BeautifyIcon

# =========================
# APP CONFIG
# =========================
st.set_page_config(page_title="🚀 Route Optimizer Pro", layout="wide")
st.title("🇳🇬 Ultra-Fast Route Optimizer (Production Stable)")

uploaded_file = st.file_uploader("📂 Upload CSV or Excel", type=["xlsx", "csv"])


# =========================
# FILE LOADER
# =========================
def load_file(file):
    name = file.name.lower()

    if name.endswith(".csv"):
        raw = pd.read_csv(file, header=None)
    else:
        raw = pd.read_excel(file, header=None)

    header_row = None

    for i, row in raw.iterrows():
        r = [str(x).lower() for x in row.values if pd.notna(x)]

        has_lat = any("lat" in x for x in r)
        has_lon = any(("lon" in x or "lng" in x) for x in r)

        if has_lat and has_lon:
            header_row = i
            break

    if header_row is None:
        st.error("❌ Could not detect header row (lat/lon missing)")
        st.stop()

    if name.endswith(".csv"):
        df = pd.read_csv(file, header=header_row)
    else:
        df = pd.read_excel(file, header=header_row)

    return df


# =========================
# CLEAN (ROBUST FIX)
# =========================
def clean(df):
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains("unnamed")]

    def find_col(keys):
        for c in df.columns:
            for k in keys:
                if k in c:
                    return c
        return None

    lat_col = find_col(["lat"])
    lon_col = find_col(["lon", "lng"])
    addr_col = find_col(["address", "site", "name", "location", "stop", "customer"])

    if not lat_col or not lon_col or not addr_col:
        st.error("❌ Missing required columns")
        st.write("Detected columns:", list(df.columns))
        st.stop()

    df = df.rename(columns={
        lat_col: "Latitude",
        lon_col: "Longitude",
        addr_col: "Address"
    })

    df = df.dropna(subset=["Latitude", "Longitude", "Address"])
    return df


# =========================
# FAST HAVERSINE
# =========================
def haversine_np(lat1, lon1, lat2, lon2):
    R = 6371000

    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


# =========================
# DISTANCE MATRIX (FAST)
# =========================
@st.cache_data(show_spinner=False)
def create_distance_matrix(locations):
    coords = np.array(locations)
    lat = coords[:, 0]
    lon = coords[:, 1]

    size = len(coords)
    matrix = np.zeros((size, size), dtype=np.int32)

    for i in range(size):
        matrix[i] = haversine_np(lat[i], lon[i], lat, lon).astype(np.int32)

    return matrix.tolist()


# =========================
# OR-TOOLS TSP (FAST + SAFE)
# =========================
def solve_tsp(distance_matrix):
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return distance_matrix[
            manager.IndexToNode(from_index)
        ][manager.IndexToNode(to_index)]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()

    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    search_params.time_limit.FromSeconds(3)
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

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
# OSRM ROUTE (FIXED)
# =========================
@st.cache_data(show_spinner=False)
def get_road_path(start, end):
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
    except:
        return None


# =========================
# MAIN APP
# =========================
if uploaded_file:

    df = load_file(uploaded_file)
    df = clean(df)

    locations = list(zip(df["Latitude"], df["Longitude"]))
    names = df["Address"].astype(str).tolist()

    st.success(f"✅ Loaded {len(locations)} locations")

    with st.spinner("⚡ Optimizing route..."):
        dist_matrix = create_distance_matrix(locations)
        route_idx = solve_tsp(dist_matrix)

    optimized_locations = [locations[i] for i in route_idx]
    optimized_names = [names[i] for i in route_idx]

    # =========================
    # MAP
    # =========================
    st.subheader("🗺️ Optimized Route Map")

    m = folium.Map(location=optimized_locations[0], zoom_start=10)

    for i, loc in enumerate(optimized_locations):
        folium.Marker(
            loc,
            tooltip=f"{i+1}. {optimized_names[i]}",
            icon=BeautifyIcon(
                number=i + 1,
                border_color="black",
                text_color="white",
                background_color="#007bff",
            ),
        ).add_to(m)

    for i in range(len(optimized_locations) - 1):
        road = get_road_path(optimized_locations[i], optimized_locations[i + 1])
        if road:
            folium.PolyLine(road, color="blue", weight=5).add_to(m)

    st_folium(m, width=1200, height=600)

    # =========================
    # RESULT TABLE
    # =========================
    st.subheader("📋 Optimized Route Order")

    result = pd.DataFrame({
        "Step": range(1, len(optimized_names) + 1),
        "Location": optimized_names,
        "Latitude": [x[0] for x in optimized_locations],
        "Longitude": [x[1] for x in optimized_locations]
    })

    st.dataframe(result, use_container_width=True)

    st.download_button(
        "⬇️ Download CSV",
        result.to_csv(index=False),
        "optimized_route.csv",
        "text/csv"
    )
