import pathlib as pl
import numpy as np
import xarray as xr
import rioxarray as rxr
import geopandas as gpd
import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide", page_title="Deforest Viewer")
st.title("Deforestation Viewer (2019-2024)")

# --- Paths ---
BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"
AOI_PATH = BASE_DIR / "data" / "aoi" / "roi.geojson"
CHANGE_DIR = BASE_DIR / "data" / "change"
CHANGE_DIR.mkdir(parents=True, exist_ok=True)

# --- Discover composites ---
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

# --- Year selector for the base NDVI layer ---
single_year = len(years) ==1
if single_year:
    year = years[0]
    st.caption(f"Only one composite found ({year}). Comparison disabled")
else:
    year = st.slider("Year", min_value=min(years), max_value=max(years), value=min(years), step=1)

tif = COMP_DIR / f"ndvi_median_{year}.tif"
tiff = COMP_DIR / f"ndvi_median_{year}.tiff"
raster_path = str(tif if tif.exists() else tiff)

# --- Map centered on AOI centroid ---
if AOI_PATH.exists():
    aoi = gpd.read_file(AOI_PATH).to_crs(4326)
    centroid = aoi.geometry.centroid.unary_union
    center = [centroid.y, centroid.x]
    zoom = 11
else:
    center = [0, 0]
    zoom = 3

m = leafmap.Map(center=center, zoom=zoom, draw_control=False, measure_control=False)
m.add_basemap("HYBRID")

# --- Base NDVI layer (consistent palette/range) ---
VMIN, VMAX = 0.0, 0.9
CMAP = "RdYlGn"
m.add_raster(raster_path, cmap=CMAP, opacity=0.9, layer_name=f"NDVI {year}")
m.add_colormap(cmap=CMAP, vmin=VMIN, vmax=VMAX, label="NDVI (green = more vegetation)")


# Compare two years
if not single_year:
    col1, col2 = st.columns(2)
    with col1:
        year1 = st.selectbox("Compare: From year", years, index=0)
    with col2:
        year2 = st.selectbox("Compare: To year", years, index=len(years) - 1)

    def open_ndvi_abs(base_dir: pl.Path, y: int) -> xr.DataArray:
        """Open a single-band NDVI GeoTIFF as DataArray and mask zeros/NaNs."""
        cand_tif = base_dir / "data" / "composites" / f"ndvi_median_{y}.tif"
        cand_tiff = base_dir / "data" / "composites" / f"ndvi_median_{y}.tiff"
        p = cand_tif if cand_tif.exists() else cand_tiff
        da = rxr.open_rasterio(str(p)).squeeze()
        # treat 0 and non-finite as nodata
        da = da.where((da != 0) & np.isfinite(da))
        return da

    ndvi_1 = open_ndvi_abs(BASE_DIR, year1)
    ndvi_2 = open_ndvi_abs(BASE_DIR, year2)

    # Align grids (exact pixel match) before subtraction
    if not (ndvi_2.rio.crs == ndvi_1.rio.crs and ndvi_2.rio.transform() == ndvi_1.rio.transform()):
        ndvi_2 = ndvi_2.rio.reproject_match(ndvi_1)

    # Compute delta only where both are valid
    valid = np.isfinite(ndvi_1.values) & np.isfinite(ndvi_2.values)
    delta = (ndvi_2 - ndvi_1).where(valid)

    # Symmetric range (avoid wash-out from outliers)
    flat = delta.values[np.isfinite(delta.values)]
    if flat.size > 0:
        p2, p98 = np.percentile(flat, [2, 98])
        vmax = float(max(abs(p2), abs(p98), 0.05))
    else:
        vmax = 0.1
    vmin, vmax = -vmax, vmax

    # Write delta as COG with nodata
    delta_tif = CHANGE_DIR / f"ndvi_delta_{year1}_{year2}.tif"
    delta = delta.rio.write_crs(ndvi_1.rio.crs, inplace=False)
    delta = delta.rio.write_nodata(-9999, inplace=False).fillna(-9999)
    delta.rio.to_raster(delta_tif, driver="COG", compress="DEFLATE")

    # Add change layer (diverging palette)
    m.add_raster(
        str(delta_tif),
        cmap="RdBu_r",  # red = loss, blue = gain
        vmin=vmin,
        vmax=vmax,
        opacity=0.85,
        layer_name=f"NDVI Change {year1}-{year2}",
    )
else:
    st.caption("Add more yearly composites to enable the change layer feature.")
# Optional auto-zoom to base raster bounds (comment out if it fights your view)
try:
    m.zoom_to_bounds(m.get_bounds(raster_path))
except Exception:
    pass

m.add_layer_control()
m.to_streamlit(height=780)