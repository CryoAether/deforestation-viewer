import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap
import numpy as np
import rioxarray as rxr
import geopandas as gpd
from typing import Tuple, List


#Streamlit app for visualizing yearly NDVI composites and ΔNDVI change
#over a user-supplied AOI. Composites are COGs written by search_download.py.


# ---- Constants ----
APP_TITLE = "Deforestation Viewer (1985–2024)"
NODATA = -9999.0
NDVI_CMAP = "RdYlGn"
DELTA_CMAP = "coolwarm"
DEFAULT_ZOOM = 10
SINGLE_OPACITY = 0.90
CONTEXT_OPACITY = 0.65
DELTA_OPACITY = 0.85

# ---- Page setup ----
st.set_page_config(layout="wide", page_title="Deforestation Viewer")
st.title(APP_TITLE)

# ---- Sidebar UI scaling (font + controls + spacing fixes) ----
st.markdown(
    """
    <style>
      /* Moderate, readable scaling */
      [data-testid="stSidebar"] * { font-size: 1.45rem !important; }

      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3 {
        font-size: 1.65rem !important;
        font-weight: 600;
        margin-bottom: 0.35rem;
      }

      /* Labels: give breathing room so they don't collide with widgets */
      [data-testid="stSidebar"] label {
        font-size: 1.45rem !important;
        line-height: 1.5 !important;
        display: block;
        margin-bottom: 0.35rem;
      }

        /* Slider formatting: prevent 'Year' label / value overlap */
        [data-testid="stSidebar"] .stSlider label {
        margin-bottom: 1.0rem !important;   /* slightly more space below 'Year' text */
        }

        [data-testid="stSidebar"] .stSlider {
        margin-top: .9rem !important;     /* pushes the entire slider down a bit */
        }

      /* Slider bubble + ticks sized to match text */
      [data-testid="stSidebar"] [data-testid="stThumbValue"],
      [data-testid="stSidebar"] [data-testid="stTickBarMin"],
      [data-testid="stSidebar"] [data-testid="stTickBarMax"] {
        font-size: 1.35rem !important;
        line-height: 1.35 !important;
      }

      /* Slightly thicker slider */
      [data-testid="stSidebar"] [role="slider"] { height: 1.1rem !important; }
      [data-testid="stSidebar"] [data-baseweb="slider"] div[aria-hidden="true"] {
        height: 0.45rem !important;
      }

      /* Select boxes (From year / To year): increase control height to avoid clipping */
      [data-testid="stSidebar"] [data-baseweb="select"] > div {
        min-height: 52px !important;
      }
      [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] {
        min-height: 52px !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
      }
      /* Dropdown menu items not clipped */
      [data-testid="stSidebar"] [data-baseweb="select"] div[role="listbox"] * {
        line-height: 1.6 !important;
      }

      /* Checkbox text (Show NDVI …) not cut off */
      [data-testid="stSidebar"] .stCheckbox {
        padding-top: 4px;
        padding-bottom: 4px;
      }
      [data-testid="stSidebar"] .stCheckbox label {
        line-height: 1.5 !important;
        white-space: normal;   /* allow wrapping for long year labels */
      }

      /* Make sure containers can grow with larger text */
      [data-testid="stSidebar"] [data-baseweb] { overflow: visible; }

      /* Gentle left padding for a cleaner look */
      [data-testid="stSidebar"] section { padding-left: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Paths ----
BASE_DIR = pl.Path(__file__).resolve().parents[1]
COMP_DIR = BASE_DIR / "data" / "composites"
CHANGE_DIR = BASE_DIR / "data" / "change"
CHANGE_DIR.mkdir(parents=True, exist_ok=True)

# ---- Discovery ----
def _composite_years() -> List[int]:
    tif_paths = list(COMP_DIR.glob("ndvi_median_*.tif")) + list(COMP_DIR.glob("ndvi_median_*.tiff"))
    years = []
    for p in tif_paths:
        parts = p.stem.split("_")
        if parts and parts[-1].isdigit():
            years.append(int(parts[-1]))
    return sorted(set(years))

years = _composite_years()
if not years:
    st.warning("No composites found.")
    st.write(f"Looked in: `{COMP_DIR}`")
    st.stop()

# ---- AOI centroid for sensible map start ----
def _default_center() -> Tuple[float, float]:
    try:
        aoi = gpd.read_file(BASE_DIR / "data" / "aoi" / "roi.geojson")
        c = aoi.geometry.centroid
        return float(c.y.mean()), float(c.x.mean())
    except Exception:
        return 0.0, 0.0

center = _default_center()

# ---- Helpers ----
def ndvi_path(y: int) -> pl.Path:
    tif = COMP_DIR / f"ndvi_median_{y}.tif"
    if tif.exists():
        return tif
    tiff = COMP_DIR / f"ndvi_median_{y}.tiff"
    if tiff.exists():
        return tiff
    raise FileNotFoundError(f"No composite found for year {y} in {COMP_DIR}")

@st.cache_data(show_spinner=False)
def open_ndvi(y: int):
    """Open a single-band NDVI COG and squeeze band dimension."""
    p = ndvi_path(y)
    da = rxr.open_rasterio(str(p)).squeeze()
    return da

@st.cache_data(show_spinner=False)
def write_delta_tif(y1: int, y2: int) -> pl.Path:
    """Compute ΔNDVI = NDVI(y2) - NDVI(y1), align grids, write cached COG."""
    out = CHANGE_DIR / f"ndvi_delta_{y1}_{y2}.tif"
    if out.exists():
        return out

    ndvi1 = open_ndvi(y1)
    ndvi2 = open_ndvi(y2)

    if not (ndvi2.rio.crs == ndvi1.rio.crs and ndvi2.rio.transform() == ndvi1.rio.transform()):
        ndvi2 = ndvi2.rio.reproject_match(ndvi1)

    delta = (ndvi2 - ndvi1)
    delta = delta.rio.write_nodata(NODATA, inplace=False).fillna(NODATA)
    delta = delta.rio.write_crs(ndvi1.rio.crs, inplace=False)
    delta.rio.to_raster(out, driver="COG", compress="DEFLATE")
    return out

@st.cache_data(show_spinner=False)
def robust_delta_range(delta_path: pl.Path) -> Tuple[float, float]:
    """Symmetric min/max from robust percentiles for stable diverging color scale."""
    da = rxr.open_rasterio(str(delta_path)).squeeze()
    vals = da.values
    mask = np.isfinite(vals) & (vals != NODATA)
    if mask.any():
        p2, p98 = np.percentile(vals[mask], [2, 98])
        mx = float(max(abs(p2), abs(p98), 0.05))
        return (-mx, mx)
    return (-0.3, 0.3)

# ---- Sidebar UI ----
st.sidebar.header("Controls")
mode = st.sidebar.radio("Mode", ["View single year", "Compare change (ΔNDVI)"])
m = leafmap.Map(center=center, zoom=DEFAULT_ZOOM, draw_control=False, measure_control=False)
m.add_basemap("Esri.WorldImagery")

if mode == "View single year":
    year = st.sidebar.slider("Year", min_value=min(years), max_value=max(years), value=min(years), step=1)
    raster_path = str(ndvi_path(year))
    m.add_raster(raster_path, cmap=NDVI_CMAP, opacity=SINGLE_OPACITY, layer_name=f"NDVI {year}")
    m.add_colormap(cmap=NDVI_CMAP, vmin=0.0, vmax=1.0, label=f"NDVI {year}")
    try:
        m.zoom_to_bounds(m.get_bounds(raster_path))
    except Exception:
        pass
else:
    y_from = st.sidebar.selectbox("From year", years, index=0)
    y_to = st.sidebar.selectbox("To year", years, index=len(years) - 1)
    st.caption(f"ΔNDVI = NDVI({y_to}) − NDVI({y_from})")

    show_context = st.sidebar.checkbox(f"Show NDVI {y_to} under ΔNDVI", value=True)

    delta_tif = write_delta_tif(y_from, y_to)
    vmin, vmax = robust_delta_range(delta_tif)

    if show_context:
        base_raster = str(ndvi_path(y_to))
        m.add_raster(base_raster, cmap=NDVI_CMAP, opacity=CONTEXT_OPACITY, layer_name=f"NDVI {y_to}")

    m.add_raster(
        str(delta_tif),
        cmap=DELTA_CMAP,
        vmin=vmin,
        vmax=vmax,
        opacity=DELTA_OPACITY,
        layer_name=f"ΔNDVI {y_from}→{y_to}",
    )
    m.add_colormap(cmap=DELTA_CMAP, vmin=vmin, vmax=vmax, label=f"ΔNDVI {y_from}→{y_to}")
    try:
        m.zoom_to_bounds(m.get_bounds(str(ndvi_path(y_to))))
    except Exception:
        pass

m.add_layer_control()
m.to_streamlit(height=780)