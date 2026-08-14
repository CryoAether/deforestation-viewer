from sqlalchemy import Column, Integer, String, Float, DateTime, Index, func, Text
from geoalchemy2 import Geometry
from database.connection import Base

class RegionOfInterest(Base):
    __tablename__ = "regions_of_interest"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Updated to MULTIPOLYGON (or generic GEOMETRY) with EPSG:4326
    geom = Column(Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_roi_geom", "geom", postgresql_using="gist"),
    )

class SatellitePointMeasurement(Base):
    __tablename__ = "satellite_measurements"
    __table_args__ = (
        Index("idx_sat_point_geom", "geom", postgresql_using="gist"),
        Index("idx_sat_point_year", "year"),
        {"postgresql_partition_by": "LIST (year)"}
    )

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, primary_key=True)
    ndvi_value = Column(Float, nullable=False)
    geom = Column(Geometry(geometry_type='POINT', srid=4326), nullable=False)