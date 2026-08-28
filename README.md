# Spatiotemporal Satellite Data Engine & Change Viewer

A high-throughput satellite data pipeline and interactive visualization dashboard for environmental trend modeling.

## Example Output

| Observation Window | Trend Observation |
|---|---|
| **2016** | High-density vegetation |
| **2024** | Minor visible index deviation |
| **2025** | Significant delta (Δ) attributed to environmental trend |

<p align="center">
  <img src="assets/readme/2016.png" width="31%" alt="Composite 2016">
  <img src="assets/readme/2024.png" width="31%" alt="Composite 2024">
  <img src="assets/readme/2025.png" width="31%" alt="Composite 2025">
</p>
<p align="center">
  <em>Temporal index progression — 2016 → 2024 → 2025</em>
</p>

---

## Architecture & Features

* **STAC Query Ingestion:** Programmatic asset discovery across multi-year temporal windows via Microsoft Planetary Computer.
* **Array Reductions:** Server-side calculation of vegetation indices (NDVI) and temporal delta ($\Delta$) aggregations.
* **Decoupled Delivery:** Asynchronous FastAPI backend delivering raster layers to an interactive TypeScript frontend.

## Tech Stack

* **Backend:** Python, FastAPI, Rasterio, NumPy
* **Frontend:** TypeScript, Vite, CSS
* **Data Source:** Microsoft Planetary Computer (STAC API)
