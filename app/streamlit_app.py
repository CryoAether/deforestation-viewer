import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide", page_title="Deforestation NDVI Viewer")
st.title("Deforestation NDVI Viewer (Yearly Median)")

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

m = leafmap.Map(center=[0, 0], zoom=2, draw_control=False, measure_control=False)
m.add_basemap("HYBRID")
m.add_raster(raster_path, cmap="RdYlGn", opacity=0.85, layer_name=f"NDVI {year}")
m.add_colormap(cmap="RdYlGn", vmin=-0.1, vmax=0.9, label="NDVI")
try:
    m.zoom_to_bounds(m.get_bounds(raster_path))
except Exception:
    pass

m.add_layer_control()
m.to_streamlit(height=780)