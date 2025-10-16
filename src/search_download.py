# src/search_download.py
from datetime import date, timedelta
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
from tqdm.auto import tqdm
from ndvi import compute_ndvi, mask_clouds
from collections import Counter

dask.config.set(scheduler="threads", num_workers=6)
ProgressBar().register()

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

# throttle: set MAX_SCENES=None to process all
_env = os.getenv("MAX_SCENES", "12").lower() #Testing phase, low value for quick results
#new
WINDOW_WEEKS = int(os.getenv("WINDOW_WEEKS", "8"))
WINDOW_START_MONTH = int(os.getenv("WINDOW_START_MONTH", "7"))  # 7 = July
WINDOW_START_DAY = int(os.getenv("WINDOW_START_DAY", "1"))
_env_norm = (_env or "").strip().lower()
MAX_SCENES = None if _env_norm in ("none", "") else int(_env_norm)
#new
def seasonal_window(year: int, start_month: int = 7, start_day: int = 1, weeks: int = 8):
    start = date(year, start_month, start_day)
    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    return (start, end)

def load_aoi(path="data/aoi/roi.geojson"):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())



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
    by_key = {}
    for it in items:
        key = (it.properties["s2:mgrs_tile"], it.datetime.date())
        if key not in by_key or it.properties["eo:cloud_cover"] < by_key[key].properties["eo:cloud_cover"]:
            by_key[key] = it
    items = list(by_key.values())
    print(f"After best-per-day-per-tile filter: {len(items)} scenes")
    # Keep only the most frequent (dominant) 1–2 tiles
    
    tiles = sorted({it.properties["s2:mgrs_tile"] for it in items})
    print(f"Keeping all tiles overlapping AOI: {tiles}")
    
    print(f"Keeping tiles {sorted(top_tiles)} → {len(items)} scenes after tile filter")
    items.sort(key=lambda it: it.datetime)  # chronological
    filtered = []
    last_for_tile = {}
    DAY_GAP = int(os.getenv("DAY_GAP", "10"))  # days between scenes per tile
    for it in items:
        tile = it.properties["s2:mgrs_tile"]
        d = it.datetime.date()
        if tile not in last_for_tile or (d - last_for_tile[tile]).days >= DAY_GAP:
            filtered.append(it)
            last_for_tile[tile] = d
    print(f"After {DAY_GAP}-day subsample: {len(filtered)} scenes")
    items = filtered
    return items

def stack_for_year(items, aoi_gdf, bands=("B04","B08","SCL"), resolution=30):
    utm = aoi_gdf.estimate_utm_crs()
    target_epsg = utm.to_epsg() if utm else 4326

    aoi_in_target = aoi_gdf.to_crs(target_epsg)
    minx, miny, maxx, maxy = aoi_in_target.total_bounds

    stack = st.stack(
        items,
        assets=list(bands),               
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

    years = [2020,2021,2022,2023,2024] #: 2020, 2021, 2022, 2023, 2024
    for y in tqdm(years,desc="Years"): #progress bar over years
        start, end = seasonal_window(
            y,
            start_month=WINDOW_START_MONTH,
            start_day=WINDOW_START_DAY,
            weeks=WINDOW_WEEKS
        )
        print(f"[{y}] Searching items {start} → {end} (cloud<25%) ...")
        items = search_items(aoi_geojson, start, end, max_cloud=25)
        print(f" [{y}] Found {len(items)} scenes")

        if not items:
            print(f"No scenes for {y}; skipping.")
            continue
        
        if isinstance(MAX_SCENES, int) and MAX_SCENES > 0 and len(items) > MAX_SCENES:
            items = items[:MAX_SCENES]
            print(f"Throttling to first {MAX_SCENES} scenes for speed...")
        print(f"[{y}] Building stack at 30m and clipping to AOI ...")
        stack = stack_for_year(items, aoi_gdf)
        print(f"[{y}] Stack ready: {tuple(stack.sizes.get(k) for k in ['time','y','x'])} (time, y, x)")

        red = stack.sel(band="B04")
        nir = stack.sel(band="B08")
        scl = stack.sel(band="SCL")

        print(f"[{y}] Masking nodata (zeros) ...")
        nodata = (red ==0) | (nir==0)
        red = red.where(~nodata)
        nir = nir.where(~nodata)

        print(f"[{y}] Computing NDVI + cloud/snow/water mask …")
        ndvi_t = compute_ndvi(red, nir)
        ndvi_t = mask_clouds(scl, ndvi_t)

        print(f"[{y}] Reducing to seasonal composite (max over time) …")
        ndvi_t = ndvi_t.chunk({"time": 1, "y": 1024, "x": 1024})
        ndvi_med = ndvi_t.max(dim="time", skipna=True)
        ndvi_med = ndvi_med.where(np.isfinite(ndvi_med))

        out_tif = outdir / f"ndvi_median_{y}.tif"
        ndvi_med.rio.write_crs(nir.rio.crs, inplace=True)
        ndvi_med.rio.write_transform(nir.rio.transform(), inplace=True)
        
        print(f"[{y}] Writing COG → {out_tif} …")  
        ndvi_med.rio.to_raster(out_tif, driver="COG", compress="DEFLATE", dtype="float32")
        print(f"Saved {out_tif}")

    print("Done.")

if __name__ == "__main__":
    main()