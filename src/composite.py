import xarray as xr
from ndvi import compute_ndvi,mask_clouds

def yearly_ndvi_composite(nc_in: str,tif_out:str):
    ds=xr.load_dataset(nc_in) #dims: time, band, y, x
    red=ds.sel(bands="B04")
    nir = ds.sel(band="B08")
    scl = ds.sel(band="SCL")

    ndvi_t=compute_ndvi(red,nir)
    ndvi_t=mask_clouds(scl,ndvi_t)

    ndvi_med=ndvi_t.median(dim="time",skipna=True)
    ndvi_med.rio.write_crs(ds.rio.crs,inplace=True)
    ndvi_med.rio.write_transform(ds.rio.transform(), inplace=True)
    ndvi_med.rio.to_raster(tif_out, driver="COG", dtype="float32", compress="LZW")
