import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap
import numpy as np
import xarray as xr
import rioxarray as rxr



st.set_page_config(layout="wide", page_title="Deforest Viewer")
st.title("Deforestation Viewer (2019-2024)")

BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"

files = sorted(list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff")))
years = sorted(int(p.stem.split("_")[-1]) for p in files)

if not years:
    st.warning("No composites found.")
    st.write(f"Looked in: `{COMP_DIR}`")
    st.write("Directory contents:")
    if COMP_DIR.exists():
        st.write([p.name for p in COMP_DIR.iterdir()])
    else:
        st.write("(directory does not exist)")
    st.stop()

year = st.slider("Year", min_value=min(years), max_value=max(years), value=min(years), step=1)

tif = COMP_DIR / f"ndvi_median_{year}.tif"
tiff = COMP_DIR / f"ndvi_median_{year}.tiff"
raster_path = str(tif if tif.exists() else tiff)

m = leafmap.Map(center=[0, 0], zoom=10, draw_control=False, measure_control=False)
m.add_basemap("HYBRID")
m.add_raster(raster_path, cmap="RdYlGn", opacity=0.85, layer_name=f"NDVI {year}")
m.add_colormap(cmap="RdYlGn", vmin=0.0, vmax=1.0, label="NDVI")

# Compare two years (you can make these UI controls later)
col1, col2 = st.columns(2)
with col1:
    year1 = st.selectbox("Compare: From year", years, index=0)
with col2:
    year2 = st.selectbox("Compare: To year", years, index=len(years) - 1)

def open_ndvi_abs(base_dir: pl.Path, y: int) -> xr.DataArray:
    p_tif = base_dir / "data" / "composites" / f"ndvi_median_{y}.tif"
    p_tiff = base_dir / "data" / "composites" / f"ndvi_median_{y}.tiff"
    p = p_tif if p_tif.exists() else p_tiff
    return rxr.open_rasterio(str(p)).squeeze()

ndvi_1 = open_ndvi_abs(BASE_DIR, year1)
ndvi_2 = open_ndvi_abs(BASE_DIR, year2)

# Reproject/align so both rasters are on the exact same grid
if not (ndvi_2.rio.crs == ndvi_1.rio.crs and ndvi_2.rio.transform() == ndvi_1.rio.transform()):
    ndvi_2 = ndvi_2.rio.reproject_match(ndvi_1)

# Compute delta only where both are valid
valid = np.isfinite(ndvi_1.values) & np.isfinite(ndvi_2.values)
delta = (ndvi_2 - ndvi_1).where(valid)

# Robust, symmetric color range (prevents wash-out)
flat = delta.values[np.isfinite(delta.values)]
if flat.size > 0:
    p2, p98 = np.percentile(flat, [2, 98])
    vmax = float(max(abs(p2), abs(p98), 0.05))  # never < ±0.05
else:
    vmax = 0.1
vmin, vmax = -vmax, vmax

# Write with explicit nodata so tileserver treats holes as transparent
change_dir = BASE_DIR / "data" / "change"
change_dir.mkdir(parents=True, exist_ok=True)
delta_tif = change_dir / f"ndvi_delta_{year1}_{year2}.tif"

delta = delta.rio.write_crs(ndvi_1.rio.crs, inplace=False)
delta = delta.rio.write_nodata(-9999, inplace=False)
delta = delta.fillna(-9999)
delta.rio.to_raster(delta_tif, driver="COG", compress="DEFLATE")

# Add to map
m.add_raster(
    str(delta_tif),
    colormap="coolwarm",
    vmin=vmin,
    vmax=vmax,
    opacity=0.8,
    layer_name=f"NDVI Change {year1}-{year2}",
)
try:
    m.zoom_to_bounds(m.get_bounds(raster_path))
except Exception:
    pass

m.add_layer_control()
m.to_streamlit(height=780)