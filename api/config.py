from __future__ import annotations
import pathlib as pl

BASE_DIR = pl.Path(__file__).resolve().parents[1]   # project root
DATA_DIR = BASE_DIR / "data"
COMP_DIR = DATA_DIR / "composites"
CHANGE_DIR = DATA_DIR / "change"
AOI_PATH = DATA_DIR / "aoi" / "roi.geojson"

NODATA = -9999.0
