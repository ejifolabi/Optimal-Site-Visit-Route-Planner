import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

st.set_page_config(page_title="Fast Route Optimizer", layout="wide")
st.title("🚀 Nigerian Route Optimizer (10x Faster - OR-Tools)")

uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])

# =========================
# FILE LOADER
# =========================
def load_file(file):
    name = file.name.lower()

    raw = pd.read_csv(file, header=None) if name.endswith('.csv') else pd.read_excel(file, header=None)

    header_row = None
    for i, row in raw.iterrows():
        r = row.astype(str).str.lower().tolist()
        if any('lat' in x for x in r) and any('lon' in x for x in r):
            header_row = i
            break

    if header_row is None:
        st.error("No header found")
        st.stop()

    df = pd.read_csv(file, header=header_row) if name.endswith('.csv') else pd.read_excel(file, header=header_row)

    return df


# =========================
# CLEAN DATA
# =========================
def clean(df):
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.contains('unnamed')]

    mapping = {}
    for c in df.columns:
        if 'lat' in c: mapping[c] = 'Latitude'
        elif 'lon' in c: mapping[c] = 'Longitude'
        elif 'address' in c or 'site' in c: mapping[c] = 'Address'
        elif 's/n' in c or c == 'sn': mapping[c] = 'S/N'

    df = df.rename(columns=mapping)
    df = df.loc[:, ~df.columns.duplicated()]

    required = ['Latitude', 'Longitude', 'Address']
    for r in required:
        if r not in df.columns:
            st.error(f"Missing {r}")
            st.stop()

    return df.dropna(subset=required)


# =========================
# DISTANCE MATRIX (FAST)
# =========================
def create_distance_matrix(locations):
    size = len(locations)
    matrix = []

    for i in range(size):
        row = []
        for j in range(size):
            if i == j:
                row.append(0)
            else:
                dist = geodesic(locations[i], locations[j]).km
                row.append(int(dist * 1000))  # meters
        matrix.append(row)

    return matrix


# =========================
# OR-TOOLS SOLVER
# =========================
def solve_tsp(distance_matrix):
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return distance_matrix[
            manager.IndexToNode(from_index)
        ][
            manager.IndexToNode(to_index)
        ]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(search_params)

    route = []
    index = routing.Start(0)

    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))

    return route


# =========================
# OSRM FOR MAP ONLY
# =========================
@st.cache_data
def get_road(start, end):
    url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
    try:
        r = requests.get(url).json()
        coords = r['routes'][0]['geometry']['coordinates']
        return [[lat, lon] for lon, lat in coords]
    except:
        return None


# =========================
# MAIN
# =========================
if uploaded_file:
    df = load_file(uploaded_file)
    df = clean(df)

    locations = list(zip(df['Latitude'], df['Longitude']))
    names = df['Address'].astype(str).values.tolist()

    st.success(f"{len(locations)} points loaded")

    with st.spinner("⚡ Computing optimal route (OR-Tools)..."):
        dist_matrix = create_distance_matrix(locations)
        route_idx = solve_tsp(dist_matrix)

    optimized_locations = [locations[i] for i in route_idx]
    optimized_names = [names[i] for i in route_idx]

    # =========================
    # MAP
    # =========================
    st.subheader("🗺️ Optimized Map")

    m = folium.Map(location=optimized_locations[0], zoom_start=10)

    for i, loc in enumerate(optimized_locations):
        folium.Marker(loc, tooltip=f"{i+1}: {optimized_names[i]}").add_to(m)

    for i in range(len(optimized_locations)-1):
        road = get_road(optimized_locations[i], optimized_locations[i+1])
        if road:
            folium.PolyLine(road, weight=6).add_to(m)

    st_folium(m, width=1200, height=600)

    # =========================
    # TABLE
    # =========================
    result = pd.DataFrame({
        "Step": range(1, len(optimized_names)+1),
        "Site": optimized_names
    })

    st.dataframe(result)

    st.download_button("Download CSV", result.to_csv(index=False), "optimized.csv")
