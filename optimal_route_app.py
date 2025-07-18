import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from openrouteservice import Client
from io import BytesIO
from fpdf import FPDF

# ========== SETUP ==========
st.set_page_config(page_title="Visit Planner", layout="wide")
st.title("📍 Location Proximity Sorter")

# ========== LOAD ORS API ==========
API_KEY = st.secrets["ORS_API_KEY"]
client = Client(key=API_KEY)

# ========== FILE UPLOAD ==========
uploaded_file = st.file_uploader("Upload an Excel file with columns: 'Address', 'Latitude', 'Longitude'", type=["xlsx"])
if not uploaded_file:
    st.warning("Please upload an Excel file to proceed.")
    st.stop()

# ========== READ DATA ==========
df = pd.read_excel(uploaded_file)
required_columns = {"Address", "Latitude", "Longitude"}
if not required_columns.issubset(df.columns):
    st.error(f"Your Excel must contain: {required_columns}")
    st.stop()

# ========== SELECT START POINT ==========
start_idx = st.selectbox("Select your current location (start point):", df["Address"])
start_row = df[df["Address"] == start_idx].iloc[0]
start_coords = (start_row["Longitude"], start_row["Latitude"])

# ========== LIMIT FOR SPEED ==========
MAX_LOCATIONS = 20
if len(df) > MAX_LOCATIONS:
    st.info(f"Showing only first {MAX_LOCATIONS} locations for performance.")
    df = df.head(MAX_LOCATIONS)

# ========== DISTANCE CALCULATION ==========
@st.cache_data(show_spinner="Calculating road distances...")
def get_sorted_by_distance(start_coords, df):
    results = []
    for _, row in df.iterrows():
        coord = (row["Longitude"], row["Latitude"])
        if coord == start_coords:
            continue
        try:
            route = client.directions(
                coordinates=[start_coords, coord],
                profile='driving-car',
                format='json'
            )
            dist_km = route['routes'][0]['summary']['distance'] / 1000  # meters to km
            results.append({
                "Address": row["Address"],
                "Latitude": row["Latitude"],
                "Longitude": row["Longitude"],
                "Distance (km)": round(dist_km, 2)
            })
        except Exception as e:
            st.error(f"Error fetching route to {row['Address']}: {e}")
    return pd.DataFrame(sorted(results, key=lambda x: x["Distance (km)"]))

# ========== COMPUTE ==========
sorted_df = get_sorted_by_distance(start_coords, df)

# ========== DISPLAY ==========
st.subheader("📌 Locations Sorted by Proximity to You")
st.dataframe(sorted_df.reset_index(drop=True), use_container_width=True)

# ========== PDF GENERATION ==========
def create_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Sorted Visit List", ln=True)

    pdf.set_font("Arial", "", 12)
    for i, row in data.iterrows():
        pdf.cell(0, 10, f"{i + 1}. {row['Address']} - {row['Distance (km)']} km", ln=True)

    buffer = BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')
    buffer.write(pdf_output)
    buffer.seek(0)
    return buffer

pdf = create_pdf(sorted_df)
st.download_button("📄 Download Visit Order (PDF)", data=pdf, file_name="visit_plan.pdf", mime="application/pdf")

# ========== MAP ==========
st.subheader("🗺️ Map of Locations")
m = folium.Map(location=[start_row["Latitude"], start_row["Longitude"]], zoom_start=10)

# Add start point
folium.Marker(
    location=[start_row["Latitude"], start_row["Longitude"]],
    popup="Start: " + start_row["Address"],
    icon=folium.Icon(color="green")
).add_to(m)

# Add sorted locations
for _, row in sorted_df.iterrows():
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=f"{row['Address']} ({row['Distance (km)']} km)",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

# Display map
st_folium(m, width=700, height=500)
