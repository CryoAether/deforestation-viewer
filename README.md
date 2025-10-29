# Deforestation Viewer: NDVI Change Detection (1985–2024)

A lightweight satellite analysis pipeline for monitoring vegetation change using **Landsat (5/7/8/9)** and **Sentinel-2** imagery through the **Microsoft Planetary Computer API**.  
The system computes yearly **NDVI (Normalized Difference Vegetation Index)** composites and visualizes deforestation trends in an interactive Streamlit map.

For full documentation and setup instructions, visit the [Deforestation Viewer Docs](https://cryoaether.github.io/deforestation-viewer/).
---

## Features

- Processes **Landsat 5–9** and **Sentinel-2** scenes from 1985–2024  
- Computes NDVI using dataset-specific scale and offset values  
- Masks clouds, water, snow, and shadows using QA and SCL bands  
- Outputs **Cloud-Optimized GeoTIFF (COG)** composites per year  
- Visualizes NDVI and ΔNDVI (change) in a **Streamlit dashboard**  
- Streams imagery efficiently via the Planetary Computer — minimal local storage required  

---

## Tech Stack

**Language:** Python  
**Core Libraries:** Dask, StackSTAC, Xarray, RioXarray, Rasterio, GeoPandas, NumPy  
**Visualization:** Streamlit, Leafmap, Matplotlib  
**Data Source:** Microsoft Planetary Computer STAC API

---

## Directory Overview

```
deforestation-viewer/
├── data/
│   ├── aoi/                # AOI GeoJSON files
│   ├── composites/         # NDVI output rasters
│   └── change/             # ΔNDVI difference layers
├── src/
│   ├── search_download.py  # NDVI composite generator
│   ├── ndvi.py             # NDVI computation & masking
│   └── streamlit_app.py    # Visualization interface
└── docs/                   # Documentation for MkDocs
```

---

## Quick Start

### 1. Set up the environment

Using the included example AOI (or [create your own](docs/create_aoi.md)):

```bash
conda create -n deforest python=3.11
conda activate deforest
pip install -r requirements.txt
```

### 2. Generate NDVI composites

For a fast test run using limited scenes:

```bash
MAX_SCENES=6 MAX_CLOUD=80 WINDOW_WEEKS=8 DAY_GAP=10 python src/search_download.py
```

This will:
- Query satellite imagery overlapping your AOI  
- Compute NDVI for each scene  
- Write yearly composites to `data/composites/`

### 3. Launch the viewer

```bash
streamlit run src/streamlit_app.py
```

Use the app’s controls to:
- View NDVI for a single year  
- Compare vegetation change between two years  

---

## Example Output

| Year | Observation |
|------|--------------|
| **1990** | Dense vegetation with minimal disturbance |
| **2005** | Visible clearing in northern region |
| **2020** | Significant NDVI decline due to deforestation |

<p align="center">
  <img src="docs/ndvi_comparison.png" width="650" alt="NDVI Comparison Example">
</p>

---

## Next Steps

- [Create your own AOI](docs/create_aoi.md)  
- [Generate NDVI composites](docs/search_download.md)  
- [Explore in Streamlit](docs/streamlit.md)  
- [Learn about NDVI computation](docs/ndvi.md)



