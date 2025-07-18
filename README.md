# 🗺️ Optimal Site Visit Route Planner

This Streamlit web app helps you **plan the most efficient route** when visiting multiple locations. Simply upload an Excel file with **latitude, longitude, and address**, and the app will:

- Compute the distances between all sites
- Solve the **Traveling Salesman Problem (TSP)** using **Google OR-Tools**
- Determine the optimal visit order to **minimize total travel distance**
- Display an **interactive route map**
- Allow you to download the itinerary as **CSV** and **PDF**

---

## 🚀 Live App

👉 [Launch the App](#)

---

## 📁 Input Format

The Excel file must contain the following columns:

| latitude | longitude | address       |
|----------|-----------|----------------|
| 6.5244   | 3.3792    | Ikeja, Lagos   |
| 7.3775   | 3.9470    | Abeokuta, Ogun |
| ...      | ...       | ...            |

- Column names should be exactly: `latitude`, `longitude`, `address` (case-insensitive).
- Ensure coordinates are in decimal format.

---

## ⚙️ Features

✅ Upload Excel files  
✅ Automatically computes pairwise distances  
✅ Efficient TSP solution using Google OR-Tools  
✅ Visualize visit order with an interactive **Folium** map  
✅ Download itinerary as **CSV** and **PDF**  
✅ Fast and user-friendly interface via **Streamlit**

---

## 🧠 Tech Stack
- Python
- Streamlit – for UI
- Pandas / NumPy – for data handling
- geopy – for calculating distances
- Google OR-Tools – to solve TSP
- Folium – for interactive maps
- fpdf – to generate PDF itinerary

## 📦 Dependencies
- streamlit
- pandas
- numpy
- geopy
- folium
- streamlit-folium
- openpyxl
- fpdfortools

## ✨ Future Features
- Estimated travel time based on speed
- Cost estimation (fuel or transport)
- Time slot scheduling
- REST API integration

## 👤 Author

Emmanuel Oludare Ejifolabi
AI & Signal Processing Enthusiast 🚀



