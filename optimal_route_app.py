import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import pdfkit
from jinja2 import Template
import base64
import os

st.set_page_config(page_title="📍 Optimal Site Visit Route Planner", layout="wide")
st.title("📍 Optimal Site Visit Route Planner")
st.markdown("Upload an Excel file containing site coordinates with columns: **Latitude, Longitude, Address** (not case-sensitive).")

@st.cache_data
def read_excel(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip().str.lower()
    required = {'latitude', 'longitude', 'address'}
    if not required.issubset(set(df.columns)):
        st.error(f"Your Excel must contain: {required}")
        return None
    df = df.rename(columns={'latitude': 'Latitude', 'longitude': 'Longitude', 'address': 'Address'})
    return df[['Latitude', 'Longitude', 'Address']]

def compute_distance(p1, p2):
    return round(geodesic(p1, p2).km, 2)

def nearest_neighbor_route(start_point, sites):
    unvisited = sites.copy()
    route = []
    current = start_point
    total_distance = 0
    while not unvisited.empty:
        unvisited["Distance"] = unvisited.apply(lambda row: compute_distance(current, (row["Latitude"], row["Longitude"])), axis=1)
        next_idx = unvisited["Distance"].idxmin()
        next_site = unvisited.loc[next_idx]
        distance = unvisited.loc[next_idx, "Distance"]
        total_distance += distance
        route.append({
            "Address": next_site["Address"],
            "Latitude": next_site["Latitude"],
            "Longitude": next_site["Longitude"],
            "Distance_from_last": distance
        })
        current = (next_site["Latitude"], next_site["Longitude"])
        unvisited = unvisited.drop(next_idx)
    return route, round(total_distance, 2)

# --- User Location ---
with st.expander("📌 Optional: Enter Your Current Location"):
    col1, col2 = st.columns(2)
    user_lat = col1.text_input("Latitude")
    user_lon = col2.text_input("Longitude")

uploaded = st.file_uploader("Upload Excel file", type=["xlsx"])

if uploaded:
    df = read_excel(uploaded)
    if df is not None:
        if user_lat and user_lon:
            try:
                start_point = (float(user_lat), float(user_lon))
            except:
                st.error("Invalid coordinates.")
                st.stop()
        else:
            start_point = (df["Latitude"].iloc[0], df["Longitude"].iloc[0])

        route, total_km = nearest_neighbor_route(start_point, df)
        st.session_state['route'] = route
        st.session_state['total_km'] = total_km

        st.success(f"✅ Route planned! Total travel distance: {total_km} km")
        st.subheader("📋 Sorted Route List")
        st.dataframe(pd.DataFrame(route))

        # --- Map ---
        st.subheader("🗺️ Route Map")
        map_style = st.selectbox("Choose map style", ["CartoDB.Positron", "CartoDB.DarkMatter", "Stamen.TonerLite", "OpenStreetMap"])
        m = folium.Map(location=[start_point[0], start_point[1]], zoom_start=12, tiles=map_style)

        folium.Marker(location=start_point, tooltip="Start (You)", icon=folium.Icon(color='green')).add_to(m)

        for idx, row in enumerate(route):
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                tooltip=f"{idx + 1}. {row['Address']}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

            if idx == 0:
                folium.PolyLine([start_point, (row["Latitude"], row["Longitude"])], color="red").add_to(m)
            else:
                folium.PolyLine([
                    (route[idx - 1]["Latitude"], route[idx - 1]["Longitude"]),
                    (row["Latitude"], row["Longitude"])
                ], color="red").add_to(m)

        st_folium(m, width=1100, height=500)

        # --- PDF Export ---
        def generate_pdf(route_data):
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
            pdf_path = "/tmp/route_report.pdf"
            pdfkit.from_string(html, pdf_path)
            return pdf_path

        if st.button("⬇️ Download Route Plan as PDF"):
            pdf_file = generate_pdf(route)
            with open(pdf_file, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="route_plan.pdf">📥 Click to download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
