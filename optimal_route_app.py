import streamlit as st
import pandas as pd
import folium
import requests
from geopy.distance import geodesic
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="Real Road Route - FIXED", layout="wide", page_icon="🛣️")
st.title("🛣️📍 Nigerian Road Route Optimizer - **ROUTE ORDER FIXED**")

st.markdown("Upload Excel → **ACTUAL road-optimized route** → Download **route order CSV**")

uploaded_file = st.file_uploader("📁 Upload Excel (Lat, Lon, Address)", type=["xlsx"])

with st.expander("📍 Start Location"):
    col1, col2 = st.columns(2)
    with col1: user_lat = st.number_input("Latitude", value=12.45, format="%.6f")
    with col2: user_lon = st.number_input("Longitude", value=4.20, format="%.6f")
    use_user_location = st.checkbox("Start from my location", value=True)

@st.cache_data(ttl=1800)
def get_osrm_route(start_coord, end_coord):
    """Get real Nigerian road geometry."""
    lon1, lat1 = start_coord[1], start_coord[0]
    lon2, lat2 = end_coord[1], end_coord[0]
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?geometries=geojson&overview=full"
    try:
        resp = requests.get(url, timeout=10)
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

def optimize_road_route(all_locations, all_names, all_sn):
    """**CRITICAL FIX**: Greedy optimization by REAL road distance."""
    st.info("🧠 Optimizing by **closest ROAD distance** (not straight line)...")
    
    # Start with copy of locations
    unvisited = list(range(len(all_locations)))
    route_order = []
    current_idx = 0  # Start at position 0
    
    progress_bar = st.progress(0)
    
    while unvisited:
        progress_bar.progress(1 - len(unvisited)/len(all_locations))
        
        # Find closest by ROAD distance
        best_dist = float('inf')
        best_next = None
        
        for idx in unvisited:
            road_data = get_osrm_route(all_locations[current_idx], all_locations[idx])
            dist = road_data['distance_km'] if road_data else geodesic(all_locations[current_idx], all_locations[idx]).km
            
            if dist < best_dist:
                best_dist = dist
                best_next = idx
        
        route_order.append(best_next)
        unvisited.remove(best_next)
        current_idx = best_next  # Move to next position
    
    # Return OPTIMIZED order (indices)
    return route_order

if uploaded_file:
    try:
        # Parse Excel
        df = pd.read_excel(uploaded_file)
        df.columns = [col.lower().strip() for col in df.columns]
        df = df.rename(columns={'latitude':'Latitude', 'longitude':'Longitude', 'address':'Address', 's/n':'S/N'})
        df = df.dropna(subset=['Latitude', 'Longitude', 'Address'])
        df = df[(df.Latitude.between(4,15)) & (df.Longitude.between(2,15))]
        
        if len(df) == 0:
            st.error("❌ No valid Nigerian coordinates!")
            st.stop()
        
        # Extract data
        locations = [(row.Latitude, row.Longitude) for _, row in df.iterrows()]
        site_names = [str(row.Address) for _, row in df.iterrows()]
        sn_numbers = [str(row.get('S/N', f'Site {i+1}')) for i, row in df.iterrows()]
        
        # Add user location if selected
        if use_user_location and (abs(user_lat) > 0.1 or abs(user_lon) > 0.1):
            locations.insert(0, (user_lat, user_lon))
            site_names.insert(0, "🚗 YOUR LOCATION")
            sn_numbers.insert(0, "START")
        
        st.success(f"✅ {len(locations)} sites loaded")
        
        # **ROUTE OPTIMIZATION** - This was missing before!
        route_indices = optimize_road_route(locations, site_names, sn_numbers)
        
        # **BUILD OPTIMIZED ROUTE DATA** - FIXED ORDER
        optimized_locations = [locations[i] for i in route_indices]
        optimized_names = [site_names[i] for i in route_indices]
        optimized_sn = [sn_numbers[i] for i in route_indices]
        
        # Calculate road distances for table
        route_segments = []
        total_distance = 0
        total_time = 0
        
        for i in range(len(optimized_locations)-1):
            road_data = get_osrm_route(optimized_locations[i], optimized_locations[i+1])
            if road_data:
                total_distance += road_data['distance_km']
                total_time += road_data['duration_min']
                route_segments.append(road_data)
            else:
                dist = geodesic(optimized_locations[i], optimized_locations[i+1]).km
                total_distance += dist
                route_segments.append(None)
        
        # **EXECUTIVE DASHBOARD**
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🛣️ Total Road Distance", f"{total_distance:.1f} km")
        col2.metric("⏱️ Drive Time", f"{total_time:.0f} min")
        col3.metric("📍 Stops", len(optimized_locations))
        col4.metric("⚡ Optimized", "✅ YES")
        
        # **ROUTE TABLE - OPTIMIZED ORDER**
        st.subheader("📋 **OPTIMIZED ROUTE ORDER**")
        route_table = []
        for i, idx in enumerate(route_indices):
            name = optimized_names[i]
            sn = optimized_sn[i]
            lat, lon = optimized_locations[i]
            
            if i > 0:
                dist = route_segments[i-1]['distance_km'] if route_segments[i-1] else "N/A"
                time_min = route_segments[i-1]['duration_min'] if route_segments[i-1] else "N/A"
            else:
                dist, time_min = 0, "START"
            
            route_table.append({
                'Step': i+1,
                'S/N': sn,
                'Site': name[:40],
                'Lat': f"{lat:.4f}",
                'Lon': f"{lon:.4f}",
                'Road Distance': dist,
                'Est Time': time_min
            })
        
        st.dataframe(pd.DataFrame(route_table), use_container_width=True)
        
        # **PERFECT GOOGLE MAPS VISUAL**
        st.subheader("🗺️ **REAL ROAD MAP** (Toggle Layers)")
        
        center_lat = sum(loc[0] for loc in optimized_locations)/len(optimized_locations)
        center_lon = sum(loc[1] for loc in optimized_locations)/len(optimized_locations)
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles=None)
        
        # Professional layers
        folium.TileLayer('OpenStreetMap', name='🛣️ Roads', attr='OpenStreetMap').add_to(m)
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            name='🛰️ Satellite', attr='Esri', opacity=0.85
        ).add_to(m)
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            name='🌄 Terrain (Rivers)', attr='Esri WorldTopo'
        ).add_to(m)
        
        # Route markers (optimized order!)
        for i, loc in enumerate(optimized_locations):
            popup = f"**Step {i+1}**<br>S/N: {optimized_sn[i]}<br>{optimized_names[i]}"
            color = "green" if i == 0 else ["blue", "orange", "red"][i%3]
            folium.Marker(
                [loc[0], loc[1]],
                popup=folium.Popup(popup, max_width=250),
                tooltip=f"Step {i+1}: {optimized_sn[i]}",
                icon=folium.Icon(icon="truck" if i==0 else "pushpin", color=color, prefix="fa")
            ).add_to(m)
        
        # **REAL ROAD LINES** (thick, colored)
        colors = ['red', 'orange', 'darkred', 'purple', 'blue', 'darkgreen']
        for i, road_data in enumerate(route_segments):
            if road_data and road_data['road_path']:
                folium.PolyLine(
                    road_data['road_path'],
                    color=colors[i % len(colors)],
                    weight=12,
                    opacity=0.9,
                    popup=f"Road {i+1}: {road_data['distance_km']}km"
                ).add_to(m)
        
        folium.LayerControl(collapsed=False).add_to(m)
        
        # FULLSCREEN MAP
        st_folium(m, width=1300, height=750, key="fixed_road_map")
        
        # **FIXED CSV DOWNLOAD - ROUTE ORDER**
        st.subheader("💾 **DOWNLOAD OPTIMIZED ROUTE**")
        csv_data = pd.DataFrame(route_table)
        csv = csv_data.to_csv(index=False)
        st.download_button(
            "📱 Field Team CSV (OPTIMIZED ORDER)", 
            csv, 
            "optimized_nigerian_route.csv",
            use_container_width=True
        )
        
        # PROOF: Show original vs optimized
        st.subheader("🔍 **Optimization Proof**")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Original Excel Order**")
            orig_df = pd.DataFrame({'S/N': sn_numbers, 'Address': site_names})
            st.dataframe(orig_df.head())
        with col2:
            st.write("**Optimized Route Order**")
            opt_df = pd.DataFrame({'Step': range(1,len(optimized_sn)+1), 'S/N': optimized_sn})
            st.dataframe(opt_df)

    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.exception(e)
