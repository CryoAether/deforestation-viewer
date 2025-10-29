# NDVI Composite Builder (search_download.py)— 

This module retrieves Landsat and Sentinel-2 imagery from the Microsoft Planetary Computer (MPC), masks clouds and invalid pixels, computes NDVI for each scene, and writes annual seasonal composites as Cloud-Optimized GeoTIFFs (COGs).

- **Input:** `data/aoi/roi.geojson` (EPSG:4326)
- **Output:** `data/composites/ndvi_median_<YEAR>.tif`
- **Years covered:** 1985–2024 (Landsat 5/7/8/9 and Sentinel-2)

---

## Overview

`search_download.py` forms the processing backbone of the Deforestation Viewer.  
It automatically selects the correct satellite dataset, retrieves imagery, builds multi-temporal stacks, computes NDVI, and outputs a single cleaned composite per year.

---

## Quick Start

1. **Prepare an AOI**  
   Ensure `data/aoi/roi.geojson` exists in EPSG:4326.  
   See [create_aoi.md](create_aoi.md) if you need guidance.

2. **Run the pipeline**  
   ```bash
   # Process all years, allow clouds up to 80%, 8-week seasonal window, 10-day de-dupe gap
   MAX_SCENES=None MAX_CLOUD=80 WINDOW_WEEKS=8 DAY_GAP=10 python src/search_download.py
   ```

3. **Inspect outputs**  
   Composites are written to `data/composites/`.  
   Load them in the Streamlit app or any GIS tool.

---

## What the Script Does

1. **Selects dataset by year**
   - 1985–2012 → Landsat 5/7 (L57)  
   - 2013–present → Landsat 8/9 (L89)  
   - 2016–present → Sentinel-2 L2A (S2)

2. **Searches scenes via STAC**
   - Filters by date range and AOI intersection  
   - Applies cloud cover threshold (`eo:cloud_cover`)  
   - Deduplicates to the lowest cloud cover per tile/day  
   - Optionally subsamples with `DAY_GAP` to limit redundancy

3. **Builds a stack with StackSTAC**
   - Clips to AOI bounds  
   - Reprojects to a UTM CRS inferred from the AOI  
   - Uses Dask for lazy evaluation (no local storage required)

4. **Computes NDVI per scene**
   - Applies dataset-specific scale and offset rules  
   - Sentinel-2: reflectance scaled by 1/10,000  
   - Landsat: reflectance scale ≈ 2.75e−05, offset ≈ −0.2  
   - NDVI formula: `(NIR − RED) / (NIR + RED)`

5. **Masks clouds, water, snow**
   - Sentinel-2: uses SCL classification  
   - Landsat: uses QA_PIXEL bitmask

6. **Creates a seasonal composite**
   - Reduces along time using `.max(dim="time")`  
   - Produces a single NDVI raster per year

7. **Writes Cloud-Optimized GeoTIFFs**
   - Saves as `float32` COGs with DEFLATE compression  
   - Ensures valid CRS and affine transform metadata

---

## Environment Variables

Tune the run directly from the command line without editing the code.

| Variable | Purpose | Example |
|-----------|----------|----------|
| `MAX_SCENES` | Limit scenes per year for speed (`None` = all). | `MAX_SCENES=None` or `MAX_SCENES=12` |
| `MAX_CLOUD` | Cloud cover threshold (%) for STAC query. | `MAX_CLOUD=60` |
| `WINDOW_WEEKS` | Length of seasonal window. | `WINDOW_WEEKS=12` → 12-week growing season |
| `WINDOW_START_MONTH` | Month where window starts. | `WINDOW_START_MONTH=7` → July |
| `WINDOW_START_DAY` | Day of month to start. | `WINDOW_START_DAY=1` |
| `DAY_GAP` | Minimum days between accepted scenes per tile. | `DAY_GAP=10` → ~1 scene every 10 days |

**Examples**
```bash
# Aggressive data pull over a longer season
MAX_SCENES=None MAX_CLOUD=85 WINDOW_WEEKS=12 DAY_GAP=8 python src/search_download.py

# Faster development run over a short window
MAX_SCENES=8 MAX_CLOUD=70 WINDOW_WEEKS=6 DAY_GAP=12 python src/search_download.py
```

---

## Controlling Years

By default:
```python
years = list(range(1985, 2025))
```

Common edits:
```python
# Single year
years = [2016]

# Span of years
years = list(range(2000, 2006))  # 2000–2005 inclusive

# Last decade
years = list(range(2015, 2025))
```

---

## Implementation Notes

### Dataset Registry (`DATASETS`)
Each dataset defines the STAC collection, band names, masking strategy, and reflectance scale/offset.  
The correct configuration is automatically selected using `select_dataset(year)`.

### Landsat Asset Resolution
Planetary Computer occasionally renames bands.  
`resolve_landsat_assets()` checks the first item to confirm the correct RED, NIR, and QA keys (e.g., `SR_B3`, `SR_B4`, `SR_B5`, or `QA_PIXEL`).

### Cloud Masking
- **Sentinel-2:** masks `SCL` categories (cloud, cirrus, snow, water, shadow)  
- **Landsat:** uses `_L8_BAD` bitmask from `QA_PIXEL`

### CRS Handling
The AOI is reprojected to an estimated UTM CRS.  
If a CRS is missing from the output, it’s written from the AOI before export.

### Performance and Memory
- Dask lazily evaluates all computations  
- `MAX_SCENES` and `DAY_GAP` limit per-year data volume  
- Chunks are tuned for balance: `{"time": 1, "y": 512, "x": 512}`

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|----------|---------------|------|
| “No scenes for year” | AOI outside coverage or too strict filters | Increase `MAX_CLOUD`, adjust `WINDOW_*`, verify AOI geometry |
| “Stack has 0 bands” | Asset mismatch | Check `resolve_landsat_assets()` and printed asset keys |
| COG write fails mid-run | Memory limits during compression | Reduce `MAX_SCENES` or shorten `WINDOW_WEEKS` |
| Colors appear wrong | Missing scale/offset or nodata handling | Confirm dataset scales and ensure zeros are masked |
| Misaligned pixels | CRS mismatch | Let the script assign CRS automatically (avoid manual reprojection) |

---

## How the Composite Is Formed

- **Per scene:** invalid pixels masked, reflectance scaled, NDVI computed  
- **Per year:** NDVI reduced with `.max(dim="time", skipna=True)`  
- **Output:** float32 COG with CRS and transform set from NIR band

Alternative reducers:
```python
# Median
ndvi_med = ndvi_t.median(dim="time", skipna=True)

# 95th percentile
ndvi_med = ndvi_t.quantile(0.95, dim="time", skipna=True)
```

---

## Next Steps

Once the composites are generated, open the viewer:

```bash
streamlit run src/streamlit.py
```

This allows interactive exploration, year comparison, and ΔNDVI visualization.

