# Troubleshooting and Common Issues

Below is a collection of frequent problems and their fixes when running the Deforestation Viewer.

---

## General Problems

| **Issue** | **Likely Cause** | **Fix** |
|------------|------------------|----------|
| No imagery found for certain years | AOI outside satellite coverage or cloud filter too strict | Increase `MAX_CLOUD`, extend `WINDOW_WEEKS`, or verify AOI location |
| AOI not showing in Streamlit | Missing or invalid `roi.geojson` | Recreate the AOI and ensure CRS is `EPSG:4326` |
| Streamlit map centers on (0,0) | AOI centroid failed to calculate | Check that `data/aoi/roi.geojson` contains a valid polygon |
| Output colors look inverted or strange | Incorrect scaling or missing nodata masking | Verify scale/offset in `DATASETS` and ensure zeros are masked before NDVI computation |
| Slow processing or crashes | AOI too large or too many scenes | Reduce AOI size, lower `WINDOW_WEEKS`, or limit `MAX_SCENES` |
| ΔNDVI map looks noisy | Raster alignment mismatch | Let script reproject automatically and rerun affected years |

---

## Installation Errors

| **Error** | **Cause** | **Solution** |
|------------|-----------|--------------|
| `ImportError: No module named stackstac` | StackSTAC not installed | Run `pip install -r requirements.txt` again |
| `gdal-config not found` | GDAL missing from Conda | Run `conda install -c conda-forge gdal` |
| `planetary_computer` import fails | Outdated package index | Run `pip install planetary-computer --upgrade` |

---

## Git or Environment Issues

| **Error** | **Cause** | **Solution** |
|------------|-----------|--------------|
| `Permission denied` when saving files | Folder not writable | Run from project root or check folder permissions |
| `fatal: Need to specify how to reconcile divergent branches` | Local Git branch behind remote | Run `git pull origin main --rebase` before pushing |
| Conda environment not activating | Typo in environment name | Check with `conda env list` and ensure you’re in `deforest` |

---

If you encounter something new, open an issue on GitHub or contact the repository maintainer.

---

Next: [NDVI Processing Pipeline →](search_download.md)