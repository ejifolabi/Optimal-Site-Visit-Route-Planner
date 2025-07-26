import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="Smart Site Visit Route Planner", layout="wide")
st.title("📍 Smart Site Visit Route Planner")

st.markdown("Upload an Excel file with **Latitude, Longitude, Address** columns (not case sensitive). Optionally, enter your current location.")

# File Upload
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# Optional starting point
user_lat = st.text_input("Enter your current latitude (optional):")
user_lon = st.text_input("Enter your current longitude (optional):")

@st.cache_data(show_spinner=False)
def load_data(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.lower()
    required = {'latitude', 'longitude', 'address'}
    if not required.issubset(set(df.columns)):
        st.error(f"Excel file must contain: {required}")
        return None
    return df[['latitude', 'longitude', 'address']]

@st.cache_data(show_spinner=False)
def sort_by_proximity(start_coord, locations):
    distances = []
    for _, row in locations.iterrows():
        coord = (row['latitude'], row['longitude'])
        dist_km = geodesic(start_coord, coord).km
        distances.append(dist_km)
    locations = locations.copy()
    locations['Distance_km'] = distances
    return locations.sort_values(by='Distance_km').reset_index(drop=True)

if uploaded_file:
    df = load_data(uploaded_file)
    if df is not None:
        if user_lat and user_lon:
            try:
                start_coord = (float(user_lat), float(user_lon))
            except ValueError:
                st.warning("Invalid coordinates. Using first address as start point.")
                start_coord = (df.iloc[0]['latitude'], df.iloc[0]['longitude'])
        else:
            start_coord = (df.iloc[0]['latitude'], df.iloc[0]['longitude'])

        st.success("Processing data...")
        sorted_df = sort_by_proximity(start_coord, df)

        # Show result
        st.subheader("📌 Locations Sorted by Proximity (in km)")
        st.dataframe(sorted_df[['address', 'Distance_km']], use_container_width=True)

        # Map
        st.subheader("🗺️ Route Map")
        m = folium.Map(location=start_coord, zoom_start=10, tiles='CartoDB positron')
        folium.Marker(location=start_coord, popup="Start", icon=folium.Icon(color='green')).add_to(m)
        for i, row in sorted_df.iterrows():
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=f"{i+1}. {row['address']} ({row['Distance_km']:.2f} km)",
                icon=folium.Icon(color='blue')
            ).add_to(m)
        st_folium(m, width=1000, height=600)

else:
    st.info("Upload an Excel file to begin.")
