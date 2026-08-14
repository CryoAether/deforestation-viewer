import os
from typing import List
import numpy as np
import xarray as xr
from dask.distributed import Client, LocalCluster
import stackstac as st

def init_dask_cluster(n_workers: int = 4, threads_per_worker: int = 2) -> Client:
    cluster = LocalCluster(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit="4GB"
    )
    client = Client(cluster)
    print(f"[Dask Engine] Dashboard available at: {client.dashboard_link}")
    return client

def parallel_temporal_reduction(
    items: List,
    assets: List[str],
    epsg: int,
    bounds: tuple,
    resolution: int,
    chunksize: int = 1024
) -> xr.DataArray:

    stack = st.stack(
        items,
        assets=assets,
        epsg=epsg,
        bounds=bounds,
        resolution=resolution,
        chunksize=chunksize,
        dtype="float32",
        fill_value=np.float32("nan")
    )
    
    red = stack.sel(band=assets[0])
    nir = stack.sel(band=assets[1])
    
    ndvi = (nir - red) / (nir + red + 1e-6)
    
    temporal_median = ndvi.median(dim="time", skipna=True)
    return temporal_median