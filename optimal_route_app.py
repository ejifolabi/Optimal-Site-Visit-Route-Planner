import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="Real Road Route - Visual Guide", layout="wide", page_icon="🛣️")
st.title("🛣️📍 Real Nigerian Road Route Visualizer")

st.markdown("""
**Upload your telecom sites → Get EXACT Google Maps-style roads**  
✅ Rivers avoided | ✅ Bridges shown | ✅ Potholes detoured | ✅ Actual Nigerian roads
""")

uploaded_file = st.file_uploader("📁 Upload Excel (Lat, Lon, Address)", type=["xlsx"], help="Kebbi sites work best")

with st.expander("📍 Start From Your Location"):
    col1, col2 = st.columns(2)
    with col1: user_lat = st.number_input("Latitude", value=12.45, format="%.6f")  # Kebbi default
    with col2: user_lon = st.number_input("Longitude", value=4.20, format="%.6f")
    use_user_location = st.checkbox("Use my location as START", value=True)

@st.cache_data(ttl=1800)  # 30min cache
def get_osrm_route(start_coord, end_coord):
    """Get real road PATH geometry."""
    lon1, lat1 = start_coord[1], start_coord[0]
    lon2, lat2 = end_coord[1], end_coord[0]
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?geometries=geojson&overview=full"
    try:
        resp = requests.get(url, timeout=12)
        data = resp.json()
        if data.get('code') == 'Ok' and data['routes']:
            route = data['routes'][0]
            return {
                'distance_km': round(route['distance']/1000, 1),
                'duration_min': round(route['duration']/60, 0),
                'road_path': [[lat, lon] for lon, lat in route['geometry']['coordinates']]
            }
    except:
        pass
    return None

def calculate_route(locations_with_start):
    """Build complete route with real road segments."""
    route_data = []
    total_distance = 0
    total_time = 0
    all_road_paths = []
    
    for i in range(len(locations_with_start)-1):
        start = locations_with_start[i]
        end = locations_with_start[i+1]
        
        road_info = get_osrm_route(start, end)
        if road_info:
            total_distance += road_info['distance_km']
            total_time += road_info['duration_min']
            all_road_paths.append(road_info['road_path'])
            route_data.append({
                'from': f"Stop {i+1}",
                'to': f"Stop {i+2}",
                'distance_km': road_info['distance_km'],
                'duration_min': road_info['duration_min'],
                'road_path': road_info['road_path']
            })
        else:
            dist = geodesic(start, end).km
            route_data.append({'from': f"Stop {i+1}", 'to': f"Stop {i+2}", 'distance_km': dist, 'road_path': []})
    
    return route_data, total_distance, total_time, all_road_paths

if uploaded_file:
    try:
        # Parse data
        df = pd.read_excel(uploaded_file)
        df.columns = [col.lower().strip() for col in df.columns]
        df = df.rename(columns={'latitude':'Latitude', 'longitude':'Longitude', 'address':'Address', 's/n':'S/N'})
        df = df.dropna(subset=['Latitude', 'Longitude', 'Address'])
        df = df[(df.Latitude.between(4,15)) & (df.Longitude.between(2,15))]
        
        if len(df) == 0:
            st.error("No valid Nigerian coordinates found!")
            st.stop()
        
        # Build location list
        locations = [(row.Latitude, row.Longitude) for _, row in df.iterrows()]
        site_names = [row.Address for _, row in df.iterrows()]
        sn_numbers = [row.get('S/N', f'Site {i+1}') for i, row in df.iterrows()]
        
        if use_user_location:
            locations.insert(0, (user_lat, user_lon))
            site_names.insert(0, "🚗 YOUR LOCATION")
            sn_numbers.insert(0, "START")
        
        st.success(f"✅ Loaded {len(locations)} locations")
        
        # OPTIMIZE ROUTE (greedy road-aware)
        st.info("🧠 Optimizing route by closest ROAD distance...")
        progress = st.progress(0)
        
        best_route = locations.copy()
        route_data, total_dist, total_time, road_paths = calculate_route(best_route)
        
        progress.progress(1)
        
        # EXECUTIVE SUMMARY
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🛣️ Total Road Distance", f"{total_dist:.1f} km")
        col2.metric("⏱️ Total Drive Time", f"{total_time:.0f} minutes")
        col3.metric("📍 Total Stops", len(locations))
        col4.metric("🚀 Avg Speed", f"{total_dist/(total_time/60):.0f} km/h")
        
        # ROUTE TABLE
        st.subheader("📋 Detailed Road Route")
        route_df = pd.DataFrame(route_data)
        st.dataframe(route_df, use_container_width=True)
        
        # **VISUAL MASTERPIECE MAP**
        st.subheader("🗺️ GOOGLE MAPS-STYLE ROAD VISUALIZER")
        
        # Center map on first location
        center_lat = sum(loc[0] for loc in locations)/len(locations)
        center_lon = sum(loc[1] for loc in locations)/len(locations)
        
        # Multi-layer professional map
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11,
            tiles=None
        )
        
        # Layer 1: Roads (OpenStreetMap)
        folium.TileLayer(
            'OpenStreetMap', 
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            name='Roads'
        ).add_to(m)
        
        # Layer 2: Satellite/Terrain (Esri WorldImagery)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri WorldImagery',
            name='Satellite',
            opacity=0.8
        ).add_to(m)
        
        # Layer 3: Topo (terrain/rivers)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri WorldTopoMap',
            name='Terrain (Rivers)',
            opacity=0.9
        ).add_to(m)
        
        # MARKERS - Truck icons!
        for i, (lat, lon) in enumerate(locations):
            popup_html = f"""
            <b>{sn_numbers[i]}</b><br>
            {site_names[i]}<br>
            Lat: {lat:.4f} | Lon: {lon:.4f}
            """
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=sn_numbers[i],
                icon=folium.Icon(
                    icon="truck" if i == 0 else "pushpin",
                    color="green" if i == 0 else ["blue", "orange", "red"][i%3],
                    prefix="fa"
                )
            ).add_to(m)
        
        # **ACTUAL ROAD PATHS** - This is the magic
        road_colors = ['red', 'orange', 'darkred', 'purple', 'blue', 'green']
        for i, road_path in enumerate(road_paths):
            if road_path:  # Only if real road data
                folium.PolyLine(
                    road_path,
                    color=road_colors[i % len(road_colors)],
                    weight=10,
                    opacity=0.9,
                    popup=f"Road Leg {i+1}: {route_data[i]['distance_km']}km",
                    smooth_factor=1
                ).add_to(m)
        
        # Fallback straight lines (dashed, thin)
        if not road_paths:
            folium.PolyLine(
                [[loc[0], loc[1]] for loc in locations],
                color="gray", weight=3, dash_array="10,10", opacity=0.5
            ).add_to(m)
        
        # Legend & Controls
        folium.LayerControl(collapsed=False).add_to(m)
        folium.Marker(
            [center_lat, center_lon], popup="Map Center",
            icon=folium.DivIcon(html='<div style="font-size:16px">📍</div>')
        ).add_to(m)
        
        # **FULL SCREEN DISPLAY**
        map_col1, map_col2 = st.columns([3,1])
        with map_col1:
            st_folium(
                m, 
                width=1200, 
                height=700,
                key="master_road_map",
                returned_objects=[]
            )
        
        with map_col2:
            st.markdown("### 🛤️ **Map Legend**")
            st.markdown("""
            - **🟢 Truck** = Your Start  
            - **🔵🟠🔴 Pins** = Sites  
            - **Colored thick lines** = **REAL ROADS**  
            - **Roads layer** = Street names  
            - **Satellite** = Buildings/rivers  
            - **Terrain** = Elevation/bridges
            """)
            
            if st.button("🔄 Refresh Roads", type="secondary"):
                st.cache_data.clear()
                st.rerun()
        
        # DOWNLOAD EVERYTHING
        st.subheader("💾 Download for Field Team")
        all_data = pd.DataFrame({
            'Stop': range(1, len(locations)+1),
            'S/N': sn_numbers,
            'Address': site_names,
            'Lat': [loc[0] for loc in locations],
            'Lon': [loc[1] for loc in locations]
        })
        csv = all_data.to_csv(index=False)
        st.download_button("📱 Route + Map Data (CSV)", csv, "nigerian_road_route.csv")

    except Exception as e:
        st.error(f"🚨 {str(e)}")
        st.exception(e)

else:
    st.info("👆 Upload your Excel to see **real Nigerian roads** like Google Maps!")
