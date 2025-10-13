import numpy as np

SCL_CLOUD_MASK = {3, 8, 9, 10}  # shadow, cloud, cloud, cirrus

def compute_ndvi(red, nir):
    red = red.astype("float32") / 10000.0
    nir = nir.astype("float32") / 10000.0
    return (nir - red) / (nir + red + 1e-6)

def mask_clouds(scl, arr):
    scl_i = scl.round().astype("int16")
    return arr.where(~np.isin(scl_i, list(SCL_CLOUD_MASK)))