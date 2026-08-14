import asyncio
import json
import os
from database.connection import engine, Base, AsyncSessionLocal
from database.models import RegionOfInterest
from geoalchemy2.shape import from_shape
from shapely.geometry import shape

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_aoi(geojson_path: str = "data/aoi/roi.geojson"):
    await init_db()
    if not os.path.exists(geojson_path):
        print(f"File not found: {geojson_path}")
        return

    with open(geojson_path, "r") as f:
        data = json.load(f)

    feature = data["features"][0] if "features" in data else data
    geom_shape = shape(feature["geometry"])

    async with AsyncSessionLocal() as session:
        roi = RegionOfInterest(
            name="Main AOI",
            description="Barren ROI Area",
            geom=from_shape(geom_shape, srid=4326)
        )
        session.add(roi)
        await session.commit()
        print("AOI successfully seeded into PostgreSQL/PostGIS database.")

if __name__ == "__main__":
    asyncio.run(seed_aoi())