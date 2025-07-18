## 🚗 Optimal Site Visit Route Planner

Plan the most efficient route for visiting multiple sites using real road distances and travel time. This tool helps you save cost and time by optimizing the visit order using **OpenRouteService (ORS)** and **OR-Tools**.

📍 Try the live app: [https://optimal-site-visit-route-planner.streamlit.app](https://optimal-site-visit-route-planner.streamlit.app)

---

### ✨ Features

* 🔁 **TSP-based route optimization** using road networks (not straight-line distance)
* 📍 **Optional user location** as starting point
* 🗺️ Uses **OpenRouteService API** for real-time road distance and duration
* 📄 Upload Excel file containing site data (lat, lon, address)
* 📊 Outputs optimized order, travel time, and distance
* 🧾 Downloadable **PDF** and **CSV** of the itinerary

---

### 📂 Input Format

Upload an Excel file (`.xlsx`) with the following **required columns**:

| address | latitude | longitude |
| ------- | -------- | --------- |
| Site A  | 7.123456 | 3.123456  |
| Site B  | 7.223456 | 3.223456  |

You may optionally enter your **current location** (latitude & longitude) to use as the starting point.

---

### 📦 Installation

```bash
pip install -r requirements.txt
```

#### `requirements.txt`:

```
streamlit
pandas
openrouteservice
numpy
fpdf
openpyxl
```

#### `packages.txt` (for Streamlit Cloud deployment):

```
libglib2.0-0
libsm6
libxrender1
libxext6
```

---

### 🛠 How It Works

* Uses **OpenRouteService** API to get the **distance and duration** matrix between all sites.
* Solves the **Travelling Salesman Problem (TSP)** using **Google OR-Tools** to find the optimal route.
* Creates a table of optimized visit order, road distances, and estimated times.
* Outputs downloadable **PDF** and **CSV** itineraries.

---

### 🧪 Run Locally

```bash
streamlit run optimal_route_app.py
```

---

### 🔐 Get Your Free ORS API Key

1. Visit [https://openrouteservice.org/dev/#/signup](https://openrouteservice.org/dev/#/signup)
2. Sign up and create a new token.
3. Replace the placeholder `YOUR_ORS_API_KEY` in the code with your key.

---

### ✅ Deployment on Streamlit Cloud

1. Push your project (including `optimal_route_app.py`, `requirements.txt`, and `packages.txt`) to GitHub.
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud) and deploy your repo.
3. Set the main file to `optimal_route_app.py`.

---

### 📄 Output Sample

| Visit Order | Address | Distance (km) | Duration (min) |
| ----------- | ------- | ------------- | -------------- |
| 1           | Site A  | 0.0           | 0.0            |
| 2           | Site B  | 5.2           | 12.3           |
| ...         | ...     | ...           | ...            |

---

### 🙋🏽‍♂️ Author

**Emmanuel Oludare Ejifolabi**
AI & Signal Processing Enthusiast
GitHub: [@ejifolabi](https://github.com/ejifolabi)

---
