# src/search_download.py
from datetime import date
from ndvi import compute_ndvi, mask_clouds
import json
import os
import pathlib as pl
import numpy as np
import xarray as xr
import geopandas as gpd
import rioxarray  # registers the `.rio` accessor for xarray
from pystac_client import Client
import planetary_computer as pc
import stackstac as st

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

# Optional throttle for first run so you don't stack thousands of scenes.
# Set to an integer (e.g., 50) for a quick test, or None to process all.
MAX_SCENES = int(os.getenv("MAX_SCENES", "50"))  # change to "None" when ready


def load_aoi(path="data/aoi/roi.geojson"):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())


def yearly_window(year: int, start_month=6, end_month=9):
    """Seasonal window for consistency (adjust as needed)."""
    return (date(year, start_month, 1), date(year, end_month, 30))


def search_items(aoi_geojson, start, end, max_cloud=25):
    client = Client.open(CATALOG)
    search = client.search(
        collections=[COLLECTION],
        intersects=aoi_geojson["features"][0]["geometry"],
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(search.items())               # modern API
    items = [pc.sign(it) for it in items]      # sign for MPC access
    return items


def stack_for_year(items, aoi_gdf, bands=("B04", "B08", "SCL"), resolution=10):
    """
    Build a (time, band, y, x) DataArray in a common grid.
    - Force a metric CRS (UTM) so resolution=10 means 10 meters
    - Constrain read to AOI bounds for speed/stability
    - Use float64 + NaN (robust with later math & encoding)
    """
    utm = aoi_gdf.estimate_utm_crs()
    target_epsg = utm.to_epsg() if utm else 4326

    aoi_in_target = aoi_gdf.to_crs(target_epsg)
    minx, miny, maxx, maxy = aoi_in_target.total_bounds

    stack = st.stack(
        items,
        assets=list(bands),                # list (not tuple)
        epsg=target_epsg,                 # fixes "Cannot pick a common CRS"
        bounds=(minx, miny, maxx, maxy),  # limit reads to AOI
        resolution=resolution,            # 10 m if UTM; degrees if EPSG:4326
        chunksize=2048,
        dtype="float64",                  # allows NaN fill_value
        fill_value=np.nan,
        rescale=False                     # scale DN→reflectance later in NDVI
    )
    return stack  # xarray.DataArray: (time, band, y, x)


def _nc_safe(da: xr.DataArray) -> xr.DataArray:
    """Strip non-serializable attrs/encodings so NetCDF write won't fail."""
    da = da.copy()
    da.attrs = {}
    for c in da.coords:
        da.coords[c].attrs = {}
    da.encoding = {}
    return da


def main():
    aoi_gdf, aoi_geojson = load_aoi("data/aoi/roi.geojson")
    outdir = pl.Path("data/interim")
    outdir.mkdir(parents=True, exist_ok=True)

    years = [2019, 2020, 2021, 2022, 2023, 2024]

    for y in years:
        start, end = yearly_window(y, 6, 9)
        items = search_items(aoi_geojson, start, end, max_cloud=25)
        print(f"Found {len(items)} scenes between {start} and {end} for {y}")

        if not items:
            print(f"No scenes for {y}; skipping.")
            continue

        # Optional: throttle for quick first success
        if isinstance(MAX_SCENES, int) and MAX_SCENES > 0 and len(items) > MAX_SCENES:
            items = items[:MAX_SCENES]
            print(f"Throttling to first {MAX_SCENES} scenes for speed...")

        stack = stack_for_year(items, aoi_gdf)
        red = stack.sel(band="B04")
        nir = stack.sel(band="B08")
        scl = stack.sel(band="SCL")

        ndvi_t = compute_ndvi(red, nir)          # returns float32 NDVI
        ndvi_t = mask_clouds(scl, ndvi_t)

        ndvi_med = ndvi_t.median(dim="time", skipna=True)

        out_tif = outdir / f"ndvi_median_{y}.tif"
        ndvi_med.rio.write_crs(nir.rio.crs, inplace=True)
        ndvi_med.rio.write_transform(nir.rio.transform(), inplace=True)
        ndvi_med.rio.to_raster(out_tif, driver="COG", compress="DEFLATE", dtype="float32")
        print(f"Saved {out_tif}")



    print("Done.")


if __name__ == "__main__":
    main()