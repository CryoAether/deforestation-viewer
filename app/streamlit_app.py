import pathlib as pl
import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(layout="wide", page_title="Deforestation NDVI Viewer")
st.title("Deforestation NDVI Viewer (Yearly Median)")

comp_dir = pl.Path("../data/composites")
years = sorted(int(p.stem.split("_")[-1]) for p in comp_dir.glob("ndvi_median_*.tif"))
if not years:
    st.warning("No composites found. Run the preprocessing pipeline first.")
    st.stop()

year = st.slider("Year", min_value=min(years), max_value=max(years), value=min(years), step=1)

m = leafmap.Map(center=[0, 0], zoom=2)
raster_path = str(comp_dir / f"ndvi_median_{year}.tif")

m.add_raster(raster_path, cmap="viridis", opacity=0.85, layer_name=f"NDVI {year}")
m.add_colormap(colors="viridis", vmin=-0.2, vmax=1.0, label="NDVI")
m.zoom_to_bounds(m.get_bounds(raster_path))
m.to_streamlit(height=750)