# app/streamlit_app.py
import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import rioxarray as rxr
import numpy as np

st.set_page_config(layout="wide", page_title="Deforestation Viewer (1985–2024)")
st.title("Deforestation Viewer (1985–2024)")

BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"

# Find all composites we actually have
files = sorted(list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")))
years = sorted({int(p.stem.split("_")[-1]) for p in files})

if not years:
    st.warning("No composites found.")
    st.write(f"Looked in: `{COMP_DIR}`")
    st.stop()

# Two selectors: Left year and Right year
c1, c2 = st.columns(2)
with c1:
    left_year = st.selectbox("Left year", years, index=0)
with c2:
    right_year = st.selectbox("Right year", years, index=len(years)-1)

# Resolve file paths
def composite_path(y: int) -> pl.Path:
    p_tif = COMP_DIR / f"ndvi_median_{y}.tif"
    p_tiff = COMP_DIR / f"ndvi_median_{y}.tiff"
    return p_tif if p_tif.exists() else p_tiff

left_path = composite_path(left_year)
right_path = composite_path(right_year)

missing = [y for y, p in [(left_year, left_path), (right_year, right_path)] if not p.exists()]
if missing:
    st.error(f"Missing composites for: {missing}. Looked in `{COMP_DIR}`.")
    st.stop()

# Center the map on AOI centroid if present, else a sane default
center = [0.0, 0.0]
try:
    aoi = gpd.read_file(BASE_DIR / "data" / "aoi" / "roi.geojson").to_crs(4326)
    c = aoi.geometry.centroid.unary_union
    center = [float(c.y), float(c.x)]
except Exception:
    pass

# Build map
m = leafmap.Map(center=center, zoom=9, draw_control=False, measure_control=False)
m.add_basemap("Esri.WorldImagery")

# Add both rasters with consistent styling (fixed NDVI scale)
left_layer_name = f"NDVI {left_year}"
right_layer_name = f"NDVI {right_year}"

# Use RdYlGn for both; fixed vmin/vmax so colors are comparable
m.add_raster(str(left_path), cmap="RdYlGn", vmin=0.0, vmax=1.0, opacity=1.0, layer_name=left_layer_name)
m.add_raster(str(right_path), cmap="RdYlGn", vmin=0.0, vmax=1.0, opacity=1.0, layer_name=right_layer_name)

# Single legend (generic NDVI), not per-side
m.add_colormap(cmap="RdYlGn", vmin=0.0, vmax=1.0, label="NDVI")

# Enable swipe: left vs right
# leafmap wraps Leaflet's SideBySide plugin via split_map on layer names
try:
    m.split_map(left_layer=left_layer_name, right_layer=right_layer_name)
except Exception:
    # Fallback: show both with the right on top if split_map isn't available
    st.warning("Swipe control not available; showing layers without swipe.")
    # (Right year will appear above left; users can toggle from layer control)
    m.add_layer_control()

# Fit to rasters’ bounds (use left as representative)
try:
    m.zoom_to_bounds(m.get_bounds(str(left_path)))
except Exception:
    pass

m.to_streamlit(height=780)