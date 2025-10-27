# 🛰️ Deforestation Viewer: NDVI Change Detection (1985–2024)

A Python-based satellite analysis pipeline for monitoring deforestation using **Landsat (5/7/8/9)** and **Sentinel-2** imagery via the **Microsoft Planetary Computer API**.  
The project computes **NDVI composites** to visualize vegetation change over time, optimized with **Dask**, **StackSTAC**, and **Streamlit** for interactive exploration.

---

## 🌍 Features
- Processes **Landsat 5–9** and **Sentinel-2** scenes (1985–2024)
- Computes **NDVI** using dataset-specific scaling and offsets
- Masks clouds, shadows, water, and snow using QA and SCL bands
- Produces **COG (Cloud-Optimized GeoTIFF)** NDVI composites per year
- Visualizes NDVI changes through a **Streamlit dashboard**  
- On-demand imagery streaming—only MBs stored locally instead of GBs

---

## ⚙️ Tech Stack
**Languages:** Python  
**Core Libraries:** Dask, StackSTAC, Xarray, Rasterio, Rioxarray, Geopandas, NumPy  
**Visualization:** Streamlit, Matplotlib  
**Data Source:** Microsoft Planetary Computer STAC API

---

## 🧭 Directory Structure
