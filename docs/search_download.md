# search_download.py — NDVI Composite Builder

This script searches Microsoft Planetary Computer (MPC) for Landsat and Sentinel-2 scenes over your AOI, masks clouds, computes NDVI per scene, and writes an annual seasonal composite as a Cloud-Optimized GeoTIFF (COG).

- Input: data/aoi/roi.geojson (EPSG:4326)
- Output: data/composites/ndvi_median_<YEAR>.tif
- Years covered: 1985 to 2024 (Landsat 5/7/8/9 + Sentinel-2)

## Quick start

1. Prepare an AOI
Make sure you have data/aoi/roi.geojson in EPSG:4326. See docs/create_aoi.md if you need help.
2. Run the pipeline with sensible defaults

```bash
# Process all years, allow clouds up to 80%, 8-week seasonal window, 10-day de-dupe gap
MAX_SCENES=None MAX_CLOUD=80 WINDOW_WEEKS=8 DAY_GAP=10 python src/search_download.py
```
3. Inspect outputs
COGs are written to data/composites/. Load them in the Streamlit app or any GIS.

## What the script does

1. Select dataset by year
  - 1985–2012 → Landsat 5/7 (L57)
  - 2013–present → Landsat 8/9 (L89)
  - 2016–present → Sentinel-2 L2A (S2)
2. Search scenes via STAC
	- Filters by date window and AOI intersection
  - Optional cloud cover cap using eo:cloud_cover
  - Deduplicates to the best cloud cover per tile per day
  - Optional date down-sampling per tile with DAY_GAP
3. Build a stack with StackSTAC
  - Clips to AOI bounds and reprojects to a UTM CRS inferred from AOI
  - Keeps arrays lazy with Dask to avoid large local storage
4.Compute NDVI per scene
  - Applies dataset-specific scale/offset rules
  - Sentinel-2: reflectance is scaled by 1/10000
  - Landsat C2: reflectance scale ≈ 2.75e-05 and offset ≈ −0.2 (your code uses those values)
  - Computes NDVI = (NIR − RED) / (NIR + RED)
5.Mask clouds, water, snow
	- Sentinel-2 uses SCL categories
  - Landsat uses QA_PIXEL bit flags
6. Compose a seasonal raster
	- Reduces along time to a single composite per year (you are using .max(dim="time"))
7. Write COG
  - Writes float32 COGs with DEFLATE compression and valid CRS/transform

## Environment variables

Tune the run without editing code.

| **Variable** | **Purpose** | **Example** |
|---------------|-------------|-------------|
| `MAX_SCENES` | Limit scenes per year for speed. `None` means all. | `MAX_SCENES=None` or `MAX_SCENES=12` |
| `MAX_CLOUD` | Cloud cover threshold percent for STAC query. | `MAX_CLOUD=60` |
| `WINDOW_WEEKS` | Length of the seasonal window. | `WINDOW_WEEKS=12` processes a 12-week growing season |
| `WINDOW_START_MONTH` | Month index where the window starts. | `WINDOW_START_MONTH=7` starts in July |
| `WINDOW_START_DAY` | Day of month to start the window. | `WINDOW_START_DAY=1` |
| `DAY_GAP` | Minimum days between accepted scenes per tile. | `DAY_GAP=10` keeps roughly one scene per tile every 10 days |

### Examples

```bash
# Aggressive data pull over a longer season
MAX_SCENES=None MAX_CLOUD=85 WINDOW_WEEKS=12 DAY_GAP=8 python src/search_download.py

# Faster dev run over a short window
MAX_SCENES=8 MAX_CLOUD=70 WINDOW_WEEKS=6 DAY_GAP=12 python src/search_download.py
```

## Controlling years

By default the script processes 1985–2024:

```
years = list(range(1985, 2025))
```
Common edits:

```
# Single year
years = [2016]

# A small span
years = list(range(2000, 2006))  # 2000–2005 inclusive

# Recent decade
years = list(range(2015, 2025))
```

## Key implementation details

- Dataset registry (DATASETS)
Each dataset defines the STAC collection, band names, mask strategy, and scale/offset. The script auto-selects the right one using select_dataset(year).
- Landsat asset resolution
MPC items sometimes label bands differently. resolve_landsat_assets(...) inspects the first item’s assets to confirm the actual keys for RED, NIR, and QA (e.g., SR_B3, SR_B4, SR_B5, QA_PIXEL, or aliases).
- Cloud masking
  - Sentinel-2: the SCL band masks classes like cloud, cirrus, snow/ice, water, shadow.
  - Landsat: uses QA_PIXEL bitmask _L8_BAD that combines standard flags.
- CRS handling
The AOI is reprojected to an estimated UTM CRS for the stack. If a CRS is missing on the stack, the script writes one from the AOI CRS before export.
- Memory performance
  - All scene reading and math are lazy with Dask arrays.
	- MAX_SCENES and DAY_GAP help cap the number of scenes per year.
	- The stack is chunked on {"time": 1, "y": 512, "x": 512} to balance IO and compute.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| “No scenes for <year>” | AOI outside coverage or too strict filters | Increase `MAX_CLOUD`, adjust `WINDOW_*`, verify AOI geometry |
| “Stack has 0 bands” | Asset key mismatch | Check `resolve_landsat_assets(...)` and the printed first-item assets |
| COG write fails mid-run | Memory pressure during compression | Reduce `MAX_SCENES`, shorten `WINDOW_WEEKS`, try smaller AOI |
| Colors look wrong | Missing scale/offset or nodata not masked | Confirm scale/offset in `DATASETS`, ensure zeros get masked before NDVI |
| Misplaced pixels | CRS or transform mismatch between bands | Let the script set CRS, avoid manual reprojection of input AOI to non-WGS84 |

## Example runs

Process a single known-good year:

```bash
MAX_SCENES=None MAX_CLOUD=80 WINDOW_WEEKS=8 DAY_GAP=10 python src/search_download.py
```
Limit to two recent years:

```
# in the file
years = [2021, 2022]
```

```bash
MAX_SCENES=None MAX_CLOUD=70 WINDOW_WEEKS=10 DAY_GAP=8 python src/search_download.py
```
Fast local test:

```
# in the file
years = [2016]
```

```bash
MAX_SCENES=6 MAX_CLOUD=70 WINDOW_WEEKS=6 DAY_GAP=12 python src/search_download.py
```

## How the composite is formed

- Per scene: mask invalid pixels, scale reflectance, compute NDVI.
- Per year: reduce along time with .max(dim="time", skipna=True) to produce a single seasonal composite.
- Output: float32 COG, compressed, with CRS and transform set from the NIR grid.

If you prefer a different reducer (median, 95th percentile), you can swap:

```
# current
ndvi_med = ndvi_t.max(dim="time", skipna=True)

# options
ndvi_med = ndvi_t.median(dim="time", skipna=True)
# or
ndvi_med = ndvi_t.quantile(0.95, dim="time", skipna=True)
```
