import numpy as np
import xarray as xr

SCL_CLOUD_MASK = {3,8,9,10}

def compute_ndvi(red: xr.DataArray, nir: xr.DataArray):
    red = red.astype("float32")
    nir = nir.astype("float32")
    return (nir-red) / (nir+red + 1e-6)

def mask_clouds(scl: xr.DataArray, arr: xr.DataArray):
    mask = ~np.isin(scl, list(SCL_CLOUD_MASK))
    return arr.where(mask)

