# Deforestation Viewer: NDVI Change Detection

A lightweight satellite analysis pipeline for monitoring vegetation change.

## Example Output

| Year | Observation |
|------|--------------|
| **2016** | Dense vegetation with minimal disturbance |
| **2024** | Minor visible deforestation damage |
| **2025** | Major shift in NDVI attributed to large drought |

<p align="center">
  <img src="assets/readme/2016.png" width="31%" alt="NDVI 1995">
  <img src="assets/readme/2024.png" width="31%" alt="NDVI 2002">
  <img src="assets/readme/2025.png" width="31%" alt="NDVI 2021">
</p>
<p align="center">
  <em>NDVI change progression — 2016 → 2024 → 2025</em>
</p>

---

## Features

- Processes Landsat 5–9 and Sentinel-2 scenes from 1985–2024  
- Computes NDVI using dataset-specific scale and offset values  
- Masks clouds, water, snow, and shadows using QA and SCL bands  
- Outputs Cloud-Optimized GeoTIFF (COG) composites per year  
- Visualizes NDVI and ΔNDVI (change) in a FastAPI + React Dashboard
- Streams imagery efficiently via the Planetary Computer — minimal local storage required  

---

## Tech Stack

**Language:** Python  
**Core Libraries:** Dask, StackSTAC, Xarray, RioXarray, Rasterio, GeoPandas, NumPy  
**Visualization:** FastAPI, React, Leafmap, Matplotlib  
**Data Source:** Microsoft Planetary Computer STAC API

---






