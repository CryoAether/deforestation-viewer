# NDVI Computation and Masking (`ndvi.py`)

This module performs Normalized Difference Vegetation Index (NDVI) calculations and masks invalid pixels such as clouds, water, and snow for both **Landsat** and **Sentinel-2** datasets.  
It is imported and called by `search_download.py` to compute annual NDVI composites.

---

## Overview

The functions in `ndvi.py` ensure that NDVI values are calculated consistently across sensors and that non-vegetation artifacts are removed before compositing.  
By isolating this logic, the main processing pipeline remains modular, easy to test, and extensible.

---

## Functions

### `compute_ndvi_mixed(red, nir, cfg)`

Computes NDVI using the formula:  
`NDVI = (NIR - Red) / (NIR + Red)`

- Applies dataset-specific scaling (`cfg["scale"]`) and offset (`cfg["offset"]`) for Landsat and Sentinel imagery.  
- Returns an NDVI array as `float32`.

**Parameters:**
- `red`: Red band array  
- `nir`: Near-Infrared band array  
- `cfg`: Dataset configuration dictionary  

**Returns:**  
A normalized NDVI array between -1 and 1.

---

### `mask_clouds(scl, arr)`

Masks invalid Sentinel-2 pixels using **Scene Classification Layer (SCL)** codes.  
Converts SCL values to integers and replaces all cloud, water, and snow classes with `NaN`.

**Key behavior:**
- Ensures only valid surface reflectance pixels remain  
- Used exclusively for Sentinel-2 (`cfg["mask"] == "s2"`)

---

### `mask_clouds_mixed(qa, arr, cfg)`

Applies the correct cloud/snow/water masking depending on dataset type.

- **Sentinel-2:**  
  Uses `SCL_BAD` class codes to filter unwanted categories.  

- **Landsat:**  
  Applies the QA bitmask `_L8_BAD` to remove clouds, cirrus, snow, and water pixels.  

This ensures all NDVI composites are generated only from valid, cloud-free data.

---

## Bitmask Definitions

| Constant | Purpose | Used For |
|-----------|----------|----------|
| `_L8_BAD` | Bitmask for Landsat QA_PIXEL flags (cloud, cirrus, snow, etc.) | Landsat 5–9 |
| `SCL_BAD` | Array of Sentinel-2 SCL class values to mask (3 = shadow, 6–11 = cloud/snow/water) | Sentinel-2 |

---

## Integration with the Pipeline

1. **`search_download.py`** loads the Red, NIR, and QA bands.  
2. `compute_ndvi_mixed()` scales reflectance and computes NDVI.  
3. `mask_clouds_mixed()` removes clouded or invalid pixels.  
4. The cleaned NDVI arrays are reduced across time into annual composites.

This modular design allows `search_download.py` to handle both Landsat and Sentinel-2 data uniformly.

---

## Visualization Guidance

You can preview the NDVI outputs using either **QGIS** or the **Streamlit app** (`streamlit_app.py`):

- Green → healthy vegetation (high NDVI)  
- Yellow to red → deforested or barren areas (low NDVI)

For clarity, consider including a before/after masking image in future documentation showing how clouds and snow are filtered out.

---

## Example Workflow

```python
from ndvi import compute_ndvi_mixed, mask_clouds_mixed

ndvi = compute_ndvi_mixed(red_band, nir_band, cfg)
clean_ndvi = mask_clouds_mixed(qa_band, ndvi, cfg)
```

The resulting `clean_ndvi` can then be passed into the compositing step in `search_download.py`.

---

## Notes

- Always use scaled reflectance inputs (not raw DN values).  
- Consistent scaling and masking are essential to ensure accurate temporal NDVI comparisons across years and sensors.  
- Outputs are written as `float32` to balance precision and file size.
