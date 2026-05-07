import geopandas as gpd
from services.load_files import SOIL_TYPES

soil_gdf = gpd.read_file(SOIL_TYPES)
soil_gdf = soil_gdf.to_crs(epsg=4326)
