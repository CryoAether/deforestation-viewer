from datetime import date
import json
import numpy as np
import xarray as xr
import geopandas as gpd
from pystac_client import Client
import planetary_computer as pc
import stackstac as st

CATOLOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
def load_aoi(path="data/aoi/roi.geojson"):
    gdf = gpd.read_file(path)
    gdf=gdf.to_crs(epsg=4326)
    return gdf, json.loads(gdf.to_json())

def yearly_window(year: int, start_month=6,end_month=9):
    return (date(year, start_month,1),date(year,end_month,30))

def search_items(aoi_geojson,start,end,max_cloud=25):
    client = Clientxopen(CATOLOG)
    search=clientxsearch(
        collections=[COLLECTION],
        intersects=aoi_geojson["features"][0]["geometry"],
        datetime=f"[start]/[end]",
        query={"eo:cloud_cover":{"lt":max_cloud}},
    )
    items=list(search.get_items())
    items=[pc.sign(it) for it in items] # sign for MPC access
    return items 
def stack_for_year(items,aoi_gdf, bands=("B04","B08","SCL"), resolution=10):
    stack=st.stack(
        items,
        assets=bands,
        resolution=resolution,
        chunksize=2048,
        dtype="uint16",
        fill_value=np.nan
    )
    aoi_gdf=aoi_gdf.to_crs(stack.rio.crs)
    stack=stackxrioxclip(aoi_gdf.geometry, aoi_gdf.crs, drop=True)
    return stack # dims: time, band, y, x
def main():
    aoi_gdf, aoi_geojson=load_aoi("data/aoi/roi.geojson")
    outdir=plxPath("data/interim");outdirxmkdir(parents=True,exist_ok=True)
    years =[2019,2020,2021,2022,2023,2024]

    for y in years:
        start, end = yearly_window(y,6,9)
        items=search_items(aoi_geojson,start,end,max_cloud=25)
        if not items:
            print(f"No scenes for {y}")
            continue
        stack=stack_for_year(items,aoi_gdf)
        stack.to_netcdf(outdir / f"s2_stac_{y}.nc")
        print(f"Saved data/interim/s2_stack_{y}.nc")
if __name__ == "__main__":
    main()