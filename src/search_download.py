# src/search_download.py
from datetime import date
import json
import os
import pathlib as pl
import numpy as np
import geopandas as gpd
import xarray as xr
import rioxarray  # registers .rio accessor
from pystac_client import Client
import planetary_computer as pc
import stackstac as st
import dask
from dask.diagnostics import ProgressBar
from ndvi import compute_ndvi, mask_clouds

dask.config.set(scheduler="threads", num_workers=6)  # tune 4–8 depending on heat

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

# throttle: set MAX_SCENES=None to process all
_env = os.getenv("MAX_SCENES", "12").lower() #Testing phase, use less than 20
_env_norm = (_env or "").strip().lower()
MAX_SCENES = None if _env_norm in ("none", "") else int(_env_norm)

def load_aoi(path="data/aoi/roi.geojson"):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())

def yearly_window(year: int, start_month=6, end_month=9):
    return (date(year, start_month, 1), date(year, end_month, 30))

def search_items(aoi_geojson, start, end, max_cloud=25):
    client = Client.open(CATALOG)
    search = client.search(
        collections=[COLLECTION],
        intersects=aoi_geojson["features"][0]["geometry"],
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    items = list(search.items())
    items = [pc.sign(it) for it in items]
    return items

def stack_for_year(items, aoi_gdf, bands=("B04","B08","SCL"), resolution=30):
    utm = aoi_gdf.estimate_utm_crs()
    target_epsg = utm.to_epsg() if utm else 4326

    aoi_in_target = aoi_gdf.to_crs(target_epsg)
    minx, miny, maxx, maxy = aoi_in_target.total_bounds

    stack = st.stack(
        items,
        assets=list(bands),                # list (not tuple)
        epsg=target_epsg,                 # common grid (UTM)
        bounds=(minx, miny, maxx, maxy),  # limit to AOI
        resolution=resolution,            # 30 m if UTM
        chunksize=2048,
        fill_value=0,
        rescale=False
    )
    stack = stack.chunk({"time": 1, "y": 1024, "x": 1024})
    return stack  # (time, band, y, x)

def main():
    aoi_gdf, aoi_geojson = load_aoi("data/aoi/roi.geojson")
    # save NDVI composites under data/composites/ (what your app expects)
    outdir = pl.Path("data/composites")
    outdir.mkdir(parents=True, exist_ok=True)

    years = [2019, 2020, 2021, 2022, 2023, 2024]
    for y in years:
        start, end = yearly_window(y, 6, 9)
        items = search_items(aoi_geojson, start, end, max_cloud=25)
        print(f"Found {len(items)} scenes between {start} and {end} for {y}")

        if not items:
            print(f"No scenes for {y}; skipping.")
            continue

        if isinstance(MAX_SCENES, int) and MAX_SCENES > 0 and len(items) > MAX_SCENES:
            items = items[:MAX_SCENES]
            print(f"Throttling to first {MAX_SCENES} scenes for speed...")

        stack = stack_for_year(items, aoi_gdf)
        red = stack.sel(band="B04")
        nir = stack.sel(band="B08")
        scl = stack.sel(band="SCL")

        nodata = (red ==0) | (nir==0)
        red = red.where(~nodata)
        nir = nir.where(~nodata)

        ndvi_t = compute_ndvi(red, nir)
        ndvi_t = mask_clouds(scl, ndvi_t)

        ndvi_t = ndvi_t.chunk({"time": 1, "y": 1024, "x": 1024})
        ndvi_med = ndvi_t.max(dim="time", skipna=True)
        ndvi_med = ndvi_med.where(np.isfinite(ndvi_med))

        out_tif = outdir / f"ndvi_median_{y}.tif"
        ndvi_med.rio.write_crs(nir.rio.crs, inplace=True)
        ndvi_med.rio.write_transform(nir.rio.transform(), inplace=True)
        
        with ProgressBar(): #progress bar
            ndvi_med.rio.to_raster(out_tif, driver="COG", compress="DEFLATE", dtype="float32")
        print(f"Saved {out_tif}")

    print("Done.")

if __name__ == "__main__":
    main()