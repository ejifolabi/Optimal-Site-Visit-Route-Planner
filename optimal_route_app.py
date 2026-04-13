import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(page_title="Real Road Route - FIXED", layout="wide", page_icon="🛣️")
st.title("🛣️📍 Nigerian Road Route Optimizer - **ROUTE ORDER FIXED**")

st.markdown("Upload Excel → **ACTUAL road-optimized route** → Download **route order CSV**")

uploaded_file = st.file_uploader("📁 Upload Excel (Lat, Lon, Address)", type=["xlsx"])

with st.expander("📍 Start Location"):
    col1, col2 = st.columns(2)
    with col1:
        user_lat = st.number_input("Latitude", value=6.34, format="%.6f")
    with col2:
        user_lon = st.number_input("Longitude", value=5.62, format="%.6f")
    use_user_location = st.checkbox("Start from my location", value=True)


# =========================
# OSRM ROAD ROUTE FUNCTION
# =========================
@st.cache_data(ttl=1800)
def get_osrm_route(start_coord, end_coord):
    lon1, lat1 = start_coord[1], start_coord[0]
    lon2, lat2 = end_coord[1], end_coord[0]

    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?geometries=geojson&overview=full"

    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if data.get('code') == 'Ok' and data['routes']:
            route = data['routes'][0]
            return {
                'distance_km': round(route['distance'] / 1000, 1),
                'duration_min': round(route['duration'] / 60, 0),
                'road_path': [[lat, lon] for lon, lat in route['geometry']['coordinates']]
            }
    except:
        pass

    return None


# =========================
# ROUTE OPTIMIZATION
# =========================
def optimize_road_route(locations):
    st.info("🧠 Optimizing by **closest ROAD distance**...")

    unvisited = list(range(len(locations)))
    route_order = []
    current_idx = 0

    progress = st.progress(0)

    while unvisited:
        progress.progress(1 - len(unvisited) / len(locations))

        best_dist = float('inf')
        best_next = None

        for idx in unvisited:
            road_data = get_osrm_route(locations[current_idx], locations[idx])
            dist = road_data['distance_km'] if road_data else geodesic(locations[current_idx], locations[idx]).km

            if dist < best_dist:
                best_dist = dist
                best_next = idx

        route_order.append(best_next)
        unvisited.remove(best_next)
        current_idx = best_next

    return route_order


# =========================
# MAIN APP
# =========================
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # 🔧 Normalize column names
        df.columns = [col.lower().strip() for col in df.columns]
        st.write("🧾 Detected Columns:", df.columns.tolist())

        # 🔄 Flexible mapping
        column_map = {}
        for col in df.columns:
            if 'lat' in col:
                column_map[col] = 'Latitude'
            elif 'lon' in col or 'lng' in col:
                column_map[col] = 'Longitude'
            elif 'address' in col or 'site' in col or 'location' in col:
                column_map[col] = 'Address'
            elif 's/n' in col or 'sn' in col:
                column_map[col] = 'S/N'

        df = df.rename(columns=column_map)

        # ✅ Validation
        required_cols = ['Latitude', 'Longitude', 'Address']
        missing = [col for col in required_cols if col not in df.columns]

        if missing:
            st.error(f"❌ Missing required columns: {missing}")
            st.stop()

        # Clean data
        df = df.dropna(subset=required_cols)
        df = df[(df.Latitude.between(4, 15)) & (df.Longitude.between(2, 15))]

        if len(df) == 0:
            st.error("❌ No valid Nigerian coordinates found")
            st.stop()

        # Extract
        locations = list(zip(df.Latitude, df.Longitude))
        names = df.Address.astype(str).tolist()
        sn = df.get('S/N', pd.Series([f"Site {i+1}" for i in range(len(df))])).astype(str).tolist()

        # Add user location
        if use_user_location:
            locations.insert(0, (user_lat, user_lon))
            names.insert(0, "🚗 YOUR LOCATION")
            sn.insert(0, "START")

        st.success(f"✅ {len(locations)} locations loaded")

        # Optimize
        route_idx = optimize_road_route(locations)

        optimized_locations = [locations[i] for i in route_idx]
        optimized_names = [names[i] for i in route_idx]
        optimized_sn = [sn[i] for i in route_idx]

        # Distance calc
        total_distance = 0
        total_time = 0
        route_segments = []

        for i in range(len(optimized_locations) - 1):
            road = get_osrm_route(optimized_locations[i], optimized_locations[i + 1])

            if road:
                total_distance += road['distance_km']
                total_time += road['duration_min']
                route_segments.append(road)
            else:
                route_segments.append(None)

        # Dashboard
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🛣️ Distance", f"{total_distance:.1f} km")
        col2.metric("⏱️ Time", f"{total_time:.0f} min")
        col3.metric("📍 Stops", len(optimized_locations))
        col4.metric("⚡ Optimized", "YES")

        # Table
        st.subheader("📋 Optimized Route")

        table = []
        for i, loc in enumerate(optimized_locations):
            lat, lon = loc

            if i == 0:
                dist, t = 0, "START"
            else:
                seg = route_segments[i - 1]
                dist = seg['distance_km'] if seg else "N/A"
                t = seg['duration_min'] if seg else "N/A"

            table.append({
                "Step": i + 1,
                "S/N": optimized_sn[i],
                "Site": optimized_names[i][:40],
                "Lat": lat,
                "Lon": lon,
                "Distance": dist,
                "Time": t
            })

        st.dataframe(pd.DataFrame(table), use_container_width=True)

        # Map
        st.subheader("🗺️ Road Map")

        center = optimized_locations[0]
        m = folium.Map(location=center, zoom_start=10)

        for i, loc in enumerate(optimized_locations):
            folium.Marker(
                loc,
                tooltip=f"Step {i+1}",
                icon=folium.Icon(color="green" if i == 0 else "blue")
            ).add_to(m)

        for seg in route_segments:
            if seg:
                folium.PolyLine(seg['road_path'], weight=8).add_to(m)

        st_folium(m, width=1200, height=600)

        # Download
        csv = pd.DataFrame(table).to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "optimized_route.csv")

    except Exception as e:
        st.error(str(e))
        st.exception(e)
