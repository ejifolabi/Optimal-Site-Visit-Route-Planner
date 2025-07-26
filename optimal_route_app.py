import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import openrouteservice
from openrouteservice import convert
from io import BytesIO
from jinja2 import Template
from xhtml2pdf import pisa

st.set_page_config(page_title="Smart Site Visit Route", layout="wide")
st.title("📍 Smart Site Visit Route Planner")
st.markdown("Upload an Excel file with: **Latitude, Longitude, Address**. Column names are not case sensitive.")

# --------------------------
# Get ORS Client (from Secrets)
@st.cache_resource
def get_ors_client():
    return openrouteservice.Client(key=st.secrets["ORS_API_KEY"])

client = get_ors_client()

# --------------------------
# Normalize Column Names
def normalize_df(df):
    df.columns = df.columns.str.strip().str.lower()
    return df.rename(columns={"latitude": "lat", "longitude": "lon", "address": "address"})

# --------------------------
# Find Closest Next Location (Greedy TSP)
def get_greedy_route(start_coords, df):
    remaining = df.copy()
    route = []
    current = start_coords
    total_distance = 0

    while not remaining.empty:
        remaining["distance"] = remaining.apply(lambda row: geodesic(current, (row["lat"], row["lon"])).km, axis=1)
        next_point = remaining.loc[remaining["distance"].idxmin()]
        total_distance += next_point["distance"]
        route.append({
            "Address": next_point["address"],
            "Latitude": next_point["lat"],
            "Longitude": next_point["lon"],
            "Distance_from_last": round(next_point["distance"], 2)
        })
        current = (next_point["lat"], next_point["lon"])
        remaining = remaining.drop(next_point.name)

    return route, round(total_distance, 2)

# --------------------------
# Plot Map with ORS route lines
def plot_route_map(start_coords, route_points):
    m = folium.Map(location=start_coords, zoom_start=10, tiles="OpenStreetMap")
    folium.Marker(location=start_coords, tooltip="Start", icon=folium.Icon(color='blue')).add_to(m)

    coords = [start_coords] + [(p["Latitude"], p["Longitude"]) for p in route_points]
    
    for i, point in enumerate(route_points):
        folium.Marker(
            location=(point["Latitude"], point["Longitude"]),
            tooltip=f"{i+1}. {point['Address']}",
            icon=folium.Icon(color="green", icon="map-marker")
        ).add_to(m)

    # ORS route
    ors_coords = [(lon, lat) for lat, lon in coords]
    try:
        res = client.directions(coordinates=ors_coords, profile='driving-car', format='geojson')
        folium.GeoJson(res, name="route").add_to(m)
    except:
        st.warning("⚠️ ORS route could not be drawn. Check API usage or coordinates.")

    return m

# --------------------------
# Generate PDF with Route Table
def generate_pdf(route_data, total_km):
    template = Template("""
    <html>
    <head><meta charset="utf-8">
    <style>
        body { font-family: Arial; }
        h2 { color: #2F80ED; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background-color: #f2f2f2; }
    </style>
    </head>
    <body>
        <h2>Optimal Site Visit Route</h2>
        <p>Total Distance: <strong>{{ total }} km</strong></p>
        <table>
            <tr>
                <th>Order</th>
                <th>Address</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Distance from Last (km)</th>
            </tr>
            {% for i, row in data %}
            <tr>
                <td>{{ i + 1 }}</td>
                <td>{{ row['Address'] }}</td>
                <td>{{ row['Latitude'] }}</td>
                <td>{{ row['Longitude'] }}</td>
                <td>{{ row['Distance_from_last'] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """)
    html = template.render(data=enumerate(route_data), total=total_km)
    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    return pdf

# --------------------------
# Excel Upload
uploaded_file = st.file_uploader("📤 Upload Excel", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = normalize_df(df)

    # Optional User Start
    with st.expander("📍 Optional: Enter Your Start Location"):
        user_lat = st.text_input("Latitude")
        user_lon = st.text_input("Longitude")
        if user_lat and user_lon:
            try:
                start_coords = (float(user_lat), float(user_lon))
            except:
                st.error("Invalid coordinates. Please use numeric values.")
                st.stop()
        else:
            start_coords = (df.iloc[0]["lat"], df.iloc[0]["lon"])
    
    # Compute Route
    with st.spinner("Calculating optimal route..."):
        route, total_km = get_greedy_route(start_coords, df)
        map_ = plot_route_map(start_coords, route)
        st.subheader(f"📏 Total Route Distance: {total_km} km")
        st_folium(map_, width=900, height=550)
        st.subheader("🗺️ Visit Order")
        st.dataframe(pd.DataFrame(route), use_container_width=True)

        # PDF
        if st.button("⬇️ Download Route Plan as PDF"):
            pdf_file = generate_pdf(route, total_km)
            st.download_button(
                label="📥 Download PDF",
                data=pdf_file.getvalue(),
                file_name="route_plan.pdf",
                mime="application/pdf"
            )
