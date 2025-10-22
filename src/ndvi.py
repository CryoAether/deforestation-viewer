import numpy as np

# shadow, water, unclassified, cloud, cloud, cirrus, snow/ice
#SCL_CLOUD_MASK = {3, 6, 7, 8, 9, 10, 11}  
_L8_BAD = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)
 # S2: shadow, water, cloud, cirrus, snow/ice
SCL_BAD = np.array([3, 6, 7, 8, 9, 10, 11], dtype=np.uint8) 

#S2 will call this
def compute_ndvi(red, nir):
    red = red.astype("float32") / 10000.0
    nir = nir.astype("float32") / 10000.0
    return (nir - red) / (nir + red + 1e-6)

#Landsat will call this
def compute_ndvi_mixed(red, nir, cfg):
    # Apply per-dataset scaling
    scale = cfg["scale"]; offset = cfg["offset"]
    redf = red * scale + offset
    nirf = nir * scale + offset
    ndvi = (nirf - redf) / (nirf + redf + 1e-6)
    return ndvi.astype("float32")

def mask_clouds(scl, arr):
    scl_i = scl.round().astype("int16")  # ensure categorical ints
    return arr.where(~np.isin(scl_i, list(SCL_BAD)))

def mask_clouds_mixed(qa, arr, cfg):
    if cfg["mask"] == "s2":
        qa_i = qa.round().astype("uint8")
        bad = np.isin(qa_i, SCL_BAD)
        return arr.where(~bad)
    else:
        # Landsat: QA_PIXEL uint16 bitmask
        qa_u = qa.astype("uint16")
        bad = (qa_u & _L8_BAD) != 0
        return arr.where(~bad)