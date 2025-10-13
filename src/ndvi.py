import numpy as np
import xarray as xr

SCL_CLOUD_MASK = {3,8,9,10} # shadow, cloud, cloud, cirrus

def compute_ndvi(red: xr.DataArray, nir: xr.DataArray):
    red = red.astype("float32") / 10000.0
    nir = nir.astype("float32") / 10000.0
    return (nir-red) / (nir+red + 1e-6)

def mask_clouds(scl: xr.DataArray, arr: xr.DataArray):
    scl_i = scl.round().astype("int16")
    mask = ~np.isin(scl_i, list(SCL_CLOUD_MASK))
    return arr.where(mask)

