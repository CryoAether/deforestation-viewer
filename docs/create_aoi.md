# 🗺️ Creating a Custom Area of Interest (AOI)

This guide walks you through creating your own **Area of Interest (AOI)** for the *Deforestation Viewer* so you can visualize NDVI change over any region you choose.

---

## 🧭 1. Install QGIS

Download and install **QGIS 3.x** from the official site:

👉 [https://qgis.org](https://qgis.org)

During installation:
- Accept the default components.
- Make sure *GDAL* support is included (it’s bundled automatically in recent versions).

After installing, open QGIS. You should see an empty map canvas.

---

## 🗺️ 2. Add a Basemap (for easy navigation)

By default, QGIS shows a blank white grid.  
You can add realistic satellite imagery using the **QuickMapServices** plugin.

### ✅ Install the QuickMapServices plugin
1. In the top menu, go to **Plugins → Manage and Install Plugins…**
2. Search for **QuickMapServices**
3. Click **Install Plugin**

### 🌍 Add a basemap
1. Once installed, go to **Web → QuickMapServices → Settings**
2. Click **More Services → Get Contributed Pack → OK**
3. Now go to **Web → QuickMapServices → ESRI → ESRI Satellite**

You should now see real satellite imagery — this helps you draw your AOI accurately.

---

## ✏️ 3. Draw Your AOI

1. In the **Layers panel**, click **New Shapefile Layer → Polygon**  
   (or **Layer → Create Layer → New GeoPackage Layer** if you prefer)
2. In the CRS dropdown, **select `EPSG:4326 (WGS84)`**
3. Click **OK**
4. Right-click your new layer → **Toggle Editing**
5. Use the **Add Polygon Feature tool** 🟩 to draw your AOI  
   (for example, outline a forest region or national park)
6. When finished, right-click → **Save Edits**, then toggle editing off.

💡 *Tip:* Keep your AOI relatively small — a few thousand km² or less — while testing. Very large areas can take hours to process.

---

## 🧾 4. Export to GeoJSON Format

The viewer expects a file named: data/aoi/roi.geojson

To export:

1. Right-click your AOI layer → **Export → Save Features As…**
2. Format: **GeoJSON**
3. CRS: **EPSG:4326 – WGS 84**
4. File name: /data/aoi/roi.geojson
5. Click **OK**
Your folder should now look like:
deforestation-viewer/
└── data/
└── aoi/
└── roi.geojson
---

## 🔍 5. Verify the AOI

### Option A — in QGIS
Re-open the saved GeoJSON file to ensure it displays correctly and covers the intended area.

### Option B — in Python
Run this quick check in your environment:
```python
import geopandas as gpd
gdf = gpd.read_file("data/aoi/roi.geojson")
print(gdf.crs, gdf.total_bounds)
```
Output should show:
EPSG:4326 and reasonable longitude/latitude bounds.

##⚙️ 6. Run the NDVI Pipeline
Once your AOI is ready, you can process all available imagery:
```MAX_SCENES=None MAX_CLOUD=80 WINDOW_WEEKS=8 DAY_GAP=10 python src/search_download.py```
The script will:
	•	Search satellite imagery overlapping your AOI.
	•	Compute NDVI composites per year.
	•	Save them in: `data/composites/ndvi_median_<YEAR>.tif`

#🧩 7. Troubleshooting

| **Issue** | **Likely Cause** | **Fix** |
|------------|------------------|----------|
| AOI not showing or blank | Wrong CRS | Reproject to `EPSG:4326` before export |
| Empty or skipped years | Area outside dataset coverage | Choose a region with Landsat/Sentinel coverage |
| Processing killed or hangs | AOI too large | Test a smaller area or limit scenes |
| Weird rectangle or misplaced polygon | Coordinates flipped (lat/lon) | Ensure GeoJSON uses longitude first |

