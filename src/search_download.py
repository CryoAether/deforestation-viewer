from datetime import date
import json
import pathlib as pl
import numpy as np
import xarray as xr
import geopandas as gpd
import rioxarray
from pystac_client import Client
import planetary_computer as pc
import stackstac as st

CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

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
    items = [pc.sign(it) for it in items]  # sign for MPC access
    return items

def stack_for_year(items, aoi_gdf, bands=("B04", "B08", "SCL"), resolution=10):
    # Use a metric CRS (UTM) so resolution=10 means 10 meters
    utm = aoi_gdf.estimate_utm_crs()
    target_epsg = utm.to_epsg() if utm else 4326

    # Limit reads to your AOI in the target CRS
    aoi_in_target = aoi_gdf.to_crs(target_epsg)
    minx, miny, maxx, maxy = aoi_in_target.total_bounds

    stack = st.stack(
        items,
        assets=list(bands),               # <-- FIX: pass a list, not a tuple
        epsg=target_epsg,                # ensure common output CRS
        bounds=(minx, miny, maxx, maxy), # constrain to AOI
        resolution=resolution,           # 10 m if UTM; degrees if 4326 fallback
        chunksize=2048,
        dtype="float64",                 # allows NaN fill
        fill_value=np.nan,               # safe nodata for later math
        rescale=False                    # scale to reflectance in compute_ndvi()
    )

    # Safety clip (already bounded above, but fine to keep)
    stack = stack.rio.clip(aoi_in_target.geometry, aoi_in_target.crs, drop=True)
    return stack
def main():
    aoi_gdf, aoi_geojson = load_aoi("data/aoi/roi.geojson")
    outdir = pl.Path("data/interim"); outdir.mkdir(parents=True, exist_ok=True)
    years = [2019, 2020, 2021, 2022, 2023, 2024]

    for y in years:
        start, end = yearly_window(y, 6, 9)
        items = search_items(aoi_geojson, start, end, max_cloud=25)
        if not items:
            print(f"No scenes for {y}")
            continue
        stack = stack_for_year(items, aoi_gdf)
        stack.to_netcdf(outdir / f"s2_stack_{y}.nc")
        print(f"Saved data/interim/s2_stack_{y}.nc")

if __name__ == "__main__":
    main()