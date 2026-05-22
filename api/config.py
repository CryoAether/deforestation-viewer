# api/config.py
from __future__ import annotations
import pathlib as pl
import numpy as np

BASE_DIR = pl.Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
COMP_DIR = DATA_DIR / "composites"
CHANGE_DIR = DATA_DIR / "change"
AOI_PATH = DATA_DIR / "aoi" / "roi.geojson"

NODATA = np.nan 