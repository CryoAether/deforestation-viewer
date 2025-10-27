import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap
import numpy as np
import rioxarray as rxr
import geopandas as gpd

st.set_page_config(layout="wide", page_title="Deforestation Viewer")
st.title("Deforestation Viewer (1985–2024)")

# --- Paths ---
BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"
CHANGE_DIR = BASE_DIR / "data" / "change"
CHANGE_DIR.mkdir(parents=True, exist_ok=True)

# Discover composites
files = sorted(list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")))
years = sorted({int(p.stem.split("_")[-1]) for p in files})

if not years:
    st.warning("No composites found.")
    st.write(f"Looked in: `{COMP_DIR}`")
    st.stop()

# AOI centroid for sensible map start
try:
    aoi = gpd.read_file(BASE_DIR / "data" / "aoi" / "roi.geojson")
    center = [aoi.geometry.centroid.y.mean(), aoi.geometry.centroid.x.mean()]
except Exception:
    center = [0, 0]

# --- Helpers ---
def ndvi_path(y: int) -> pl.Path:
    tif = COMP_DIR / f"ndvi_median_{y}.tif"
    tiff = COMP_DIR / f"ndvi_median_{y}.tiff"
    return tif if tif.exists() else tiff

def open_ndvi(y: int):
    p = ndvi_path(y)
    da = rxr.open_rasterio(str(p)).squeeze()
    return da

def write_delta_tif(y1: int, y2: int) -> pl.Path:
    out = CHANGE_DIR / f"ndvi_delta_{y1}_{y2}.tif"
    if out.exists():
        return out
    ndvi1 = open_ndvi(y1)
    ndvi2 = open_ndvi(y2)
    # align grids if needed
    if not (ndvi2.rio.crs == ndvi1.rio.crs and ndvi2.rio.transform() == ndvi1.rio.transform()):
        ndvi2 = ndvi2.rio.reproject_match(ndvi1)
    delta = (ndvi2 - ndvi1)
    # set nodata explicitly so tiles are transparent
    delta = delta.rio.write_nodata(-9999, inplace=False).fillna(-9999)
    delta = delta.rio.write_crs(ndvi1.rio.crs, inplace=False)
    delta.rio.to_raster(out, driver="COG", compress="DEFLATE")
    return out

def robust_delta_range(delta_path: pl.Path):
    da = rxr.open_rasterio(str(delta_path)).squeeze()
    vals = da.values
    mask = np.isfinite(vals) & (vals != -9999)
    if mask.any():
        p2, p98 = np.percentile(vals[mask], [2, 98])
        mx = float(max(abs(p2), abs(p98), 0.05))
        return (-mx, mx)
    return (-0.3, 0.3)

# --- UI Mode ---
mode = st.radio("Mode", ["View single year", "Compare change (ΔNDVI)"], horizontal=True)

# Build map
m = leafmap.Map(center=center, zoom=10, draw_control=False, measure_control=False)
m.add_basemap("Esri.WorldImagery")

if mode == "View single year":
    year = st.slider("Year", min_value=min(years), max_value=max(years), value=min(years), step=1)
    raster_path = str(ndvi_path(year))
    m.add_raster(raster_path, cmap="RdYlGn", opacity=0.9, layer_name=f"NDVI {year}")
    m.add_colormap(cmap="RdYlGn", vmin=0.0, vmax=1.0, label=f"NDVI {year}")
    try:
        m.zoom_to_bounds(m.get_bounds(raster_path))
    except Exception:
        pass
else:
    c1, c2 = st.columns(2)
    with c1:
        y_from = st.selectbox("Compare: From year", years, index=0)
    with c2:
        y_to = st.selectbox("Compare: To year", years, index=len(years) - 1)

    st.caption(f"ΔNDVI = NDVI({y_to}) − NDVI({y_from})")

    # optional context layer
    show_context = st.checkbox(f"Show NDVI {y_to} under change layer", value=True)

    delta_tif = write_delta_tif(y_from, y_to)
    vmin, vmax = robust_delta_range(delta_tif)

    if show_context:
        base_raster = str(ndvi_path(y_to))
        m.add_raster(base_raster, cmap="RdYlGn", opacity=0.65, layer_name=f"NDVI {y_to}")

    m.add_raster(
        str(delta_tif),
        colormap="coolwarm",
        vmin=vmin,
        vmax=vmax,
        opacity=0.85,
        layer_name=f"ΔNDVI {y_from}→{y_to}",
    )
    m.add_colormap(cmap="coolwarm", vmin=vmin, vmax=vmax, label=f"ΔNDVI {y_from}→{y_to}")

    try:
        bounds_src = str(ndvi_path(y_to))
        m.zoom_to_bounds(m.get_bounds(bounds_src))
    except Exception:
        pass

m.add_layer_control()
m.to_streamlit(height=780)