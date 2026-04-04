import geopandas as gpd

soil_gdf = gpd.read_file(r"C:\Users\debas\OneDrive\Desktop\Final Year Project\Main_prj\new ds\soil_map_ref\WB_SOIL_SHP.shp")
soil_gdf = soil_gdf.to_crs(epsg=4326)