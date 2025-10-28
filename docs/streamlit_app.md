# 🌿 Streamlit App Guide — Deforestation Viewer

This page explains how to run the Streamlit map, compare years, tune the visualization, and adjust code paths when needed.

What it does:  
Renders yearly NDVI composites and an interactive change layer (ΔNDVI) over your AOI using a Leaflet map inside Streamlit.

## 1) Quick Start

### Prerequisites

- You have generated NDVI composites with `src/search_download.py`. (Output files live in `data/composites/ndvi_median_<YEAR>.tif`.)
- Your AOI is in `data/aoi/roi.geojson` with CRS EPSG:4326.

### Run
Be sure you're in the repo root and run:
`streamlit run src/streamlit_app.py`
The app will auto-discover raster files in data/composites/ and list the years.
![Deforestation Viewer — Single year mode](../assets/streamlit/single-year.png)

## 2) Using the App

### Modes

You can switch modes at the top:  
- **View single year** 
A slider selects one year. The app displays NDVI <year> with a green to red scale.
  - Green ~ healthy vegetation
  - Red ~ low vegetation or disturbance
- **Compare change (ΔNDVI)**
- Choose From year and To year. The app computes a difference raster on the fly:
`\Delta \text{NDVI} = \text{NDVI}(\text{To}) - \text{NDVI}(\text{From})`
  - Positive values indicate greening. Negative values indicate loss.
![Year slider](../assets/streamlit/year-slider.png)
![Change compare controls](../assets/streamlit/change-controls.png)

### Map Basics
- Basemap: Esri.WorldImagery (high-res satellite context).
- Map centers on your AOI centroid if available.
- Use the layer control to toggle layers.

## 3) Getting the Most Out of It

### **Pick useful year pairs**
- Try 2016 → 2020, 2000 → 2021, or pre-event vs post-event periods.
- Narrow geographic AOIs for fast interaction.

### **Normalize change smartly**
ΔNDVI can have outliers. The app derives symmetric min/max from the 2nd and 98th percentiles:  
`vmin, vmax = robust_delta_range(delta_tif)`  
This keeps the visualization stable across regions.

## 4) File and Path Layout

- Composites directory:
```
data/composites/
├── ndvi_median_1985.tif
├── ndvi_median_1986.tif
└── ...
```
- AOI: `data/aoi/roi.geojson`
- Change rasters (created on demand): `data/change/ndvi_delta_<FROM>_<TO>.tif`

## 5) Understanding the Code

The app source is tailored for clarity. Below are the key hooks you might want to tweak.

### Directory assumptions

```
BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"
CHANGE_DIR = BASE_DIR / "data" / "change"
CHANGE_DIR.mkdir(parents=True, exist_ok=True)
```
Adjust directory/names if you relocate outputs.

### Discover available years

```
files = sorted(list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")))
years = sorted({int(p.stem.split("_")[-1]) for p in files})
```
- This auto-detects years from filenames.
- If you change the composite filename pattern, update the glob accordingly.

### Centering on AOI

```
aoi = gpd.read_file(BASE_DIR / "data" / "aoi" / "roi.geojson")
center = [aoi.geometry.centroid.y.mean(), aoi.geometry.centroid.x.mean()]
```
If your AOI is large or multi-part, this gives a reasonable map start.
Fallback center is [0, 0] if the AOI is missing.

### Reading rasters and aligning grids

```
def open_ndvi(y: int):
    p = ndvi_path(y)
    da = rxr.open_rasterio(str(p)).squeeze()
    return da
```
- Uses rioxarray to open the COG.
- squeeze() collapses extra band dimensions if present

```
def write_delta_tif(y1: int, y2: int) -> pl.Path:
    ndvi1 = open_ndvi(y1)
    ndvi2 = open_ndvi(y2)
    if not (ndvi2.rio.crs == ndvi1.rio.crs and ndvi2.rio.transform() == ndvi1.rio.transform()):
        ndvi2 = ndvi2.rio.reproject_match(ndvi1)
    delta = (ndvi2 - ndvi1)
    delta = delta.rio.write_nodata(-9999, inplace=False).fillna(-9999)
    delta = delta.rio.write_crs(ndvi1.rio.crs, inplace=False)
    delta.rio.to_raster(out, driver="COG", compress="DEFLATE")
```
- Ensures both years are on the same grid before differencing.
- Writes ΔNDVI once and reuses it later for speed.
- You can change nodata from -9999 to something else if needed, but keep it consistent.

### Color range for ΔNDVI

```
def robust_delta_range(delta_path: pl.Path):
    p2, p98 = np.percentile(vals[mask], [2, 98])
    mx = float(max(abs(p2), abs(p98), 0.05))
    return (-mx, mx)
```
- Symmetric scaling around zero helps you compare loss vs gain fairly.
- Raise the minimum floor from 0.05 to 0.1 if the change looks too muted.

### Map layer styling

**Single year:**

```
m.add_raster(raster_path, cmap="RdYlGn", opacity=0.9, layer_name=f"NDVI {year}")
m.add_colormap(cmap="RdYlGn", vmin=0.0, vmax=1.0, label=f"NDVI {year}")
```
- Swap cmap to another Matplotlib colormap string if you prefer a different palette e.g. (PuBuGn, YlGn etc...)
- Keep vmin=0.0, vmax=1.0 since NDVI is scaled to [0, 1].

**Multi year mode:**

```
m.add_raster(str(delta_tif), colormap="coolwarm", vmin=vmin, vmax=vmax, opacity=0.85, layer_name=f"ΔNDVI {y_from}→{y_to}")
m.add_colormap(cmap="coolwarm", vmin=vmin, vmax=vmax, label=f"ΔNDVI {y_from}→{y_to}")
```

- You can switch to bwr or RdBu if you want a different diverging scheme.

![Single year NDVI](../assets/streamlit/ndvi-layer.png)
![ΔNDVI layer](../assets/streamlit/delta-layer.png)

## 6) Tips for Performance

- Smaller AOIs render faster.
- Avoid comparing extremely distant years when testing.
- If map tiling feels slow, close other heavy apps and ensure the composites were generated with reasonable chunk sizes.

## 7) Common Troubleshooting

| **Symptom** | **Likely Cause** | **Fix** |
|--------------|------------------|----------|
| No years found | Composites not generated or filename pattern changed | Run the pipeline or update the glob pattern in `COMP_DIR.glob(...)` |
| Map centers to 0,0 | AOI missing or invalid | Place `data/aoi/roi.geojson` with valid geometry, CRS `EPSG:4326` |
| ΔNDVI looks noisy | Mismatch in grids before differencing | The app already reprojects. Re-run if source files changed |
| Colors look off | `vmin/vmax` too tight or too wide | Adjust `robust_delta_range` floor or set fixed `vmin/vmax` manually |
