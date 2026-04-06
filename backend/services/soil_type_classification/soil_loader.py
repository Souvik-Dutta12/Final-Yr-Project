import geopandas as gpd

soil_gdf = gpd.read_file(r"C:\Users\basud\OneDrive\Documents\MERN PROJECTS\Final-Yr-Project\new ds\soil_map_ref\WB_SOIL_SHP.shp")
soil_gdf = soil_gdf.to_crs(epsg=4326)


# from pathlib import Path
# import geopandas as gpd

# BASE_DIR = Path(__file__).resolve().parent.parent.parent
# soil_file = BASE_DIR / "soil_map_ref" / "WB_SOIL_SHP.shp"

# soil_gdf = gpd.read_file(soil_file)