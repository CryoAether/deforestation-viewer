# 🌿 NDVI Computation and Masking (`ndvi.py`)

This module handles all vegetation index (NDVI) calculations and masking of invalid pixels (clouds, water, snow) for both **Landsat** and **Sentinel-2** datasets.  
It’s imported and used by `search_download.py` to compute yearly NDVI composites.

---

## ⚙️ Functions Overview

- **`compute_ndvi_mixed(red, nir, cfg)`**  
  Computes NDVI using the formula:  
  *(NIR - Red) / (NIR + Red)*,  
  applying dataset-specific scaling (`cfg["scale"]`) and offset (`cfg["offset"]`) for Landsat and Sentinel imagery.  
  Returns an NDVI array as `float32`.  
  - Inputs: red band, NIR band, dataset config (`cfg`)  
  - Output: normalized NDVI array between -1 and 1

- **`mask_clouds(scl, arr)`**  
  Masks out invalid Sentinel-2 pixels (e.g., cloud, water, snow) using **Scene Classification Layer (SCL)** codes.  
  Converts class codes to integers and replaces bad pixels with `NaN`.

- **`mask_clouds_mixed(qa, arr, cfg)`**  
  Applies appropriate masking depending on dataset:  
  - For **Sentinel-2** (`cfg["mask"] == "s2"`): uses `SCL_BAD` classes.  
  - For **Landsat**: uses QA bitmask (`_L8_BAD`) to remove cloud, cirrus, and snow-covered pixels.  
  Ensures only valid surface reflectance values contribute to NDVI composites.

---

## 🧠 Bitmask Definitions

| Constant | Purpose | Used For |
|-----------|----------|-----------|
| `_L8_BAD` | Bitmask for Landsat QA_PIXEL flags (cloud, cirrus, snow, etc.) | Landsat 5–9 |
| `SCL_BAD` | Array of Sentinel-2 SCL class values to mask (3 = shadow, 6–11 = cloud/snow/water) | Sentinel-2 |

---

## 🔍 How It Fits in the Pipeline

1. **`search_download.py`** loads Red/NIR/QA bands.  
2. `compute_ndvi_mixed()` calculates NDVI values using scaled reflectance.  
3. `mask_clouds_mixed()` removes invalid pixels.  
4. The cleaned NDVI values are aggregated into yearly composites.  

---

## 🖼️ Visualization Tip

You can visualize raw NDVI outputs in QGIS or Streamlit (`streamlit_app.py`):  
- Green = healthy vegetation (high NDVI)  
- Red = barren or deforested areas (low NDVI)  

🧩 *Consider adding a small side-by-side image here showing before/after masking for clarity.*
