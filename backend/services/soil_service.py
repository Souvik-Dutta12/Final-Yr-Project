from shapely.geometry import Point,shape
from services.soil_loader import soil_gdf
import geopandas as gpd

def get_soil_type(lat, lon):
    point = Point(lon, lat)  # IMPORTANT: (lon, lat)

    # find polygon containing point
    matches = soil_gdf[soil_gdf.contains(point)]

    if not matches.empty:
        soil = matches.iloc[0]["soil_class"]

        if str(soil).lower() != "other":
            return soil
        
    # fallback → nearest soil
    temp = soil_gdf.copy()
    temp = temp[~temp["soil_class"].str.lower().str.contains("other")]
    temp["distance"] = temp.distance(point)
    nearest = temp.sort_values("distance").iloc[0]
    return nearest["soil_class"]

def get_soil_distribution(polygon):
    polygon = shape(polygon)

    # convert polygon → GeoDataFrame
    poly_gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")

    # intersection
    intersection = gpd.overlay(soil_gdf, poly_gdf, how="intersection")

    if intersection.empty:
        return []

    # calculate area
    intersection["area"] = intersection.geometry.area

    total_area = intersection["area"].sum()

    # group by soil type
    result = (
        intersection.groupby("soil_class")["area"]
        .sum()
        .reset_index()
    )

    result["percentage"] = (result["area"] / total_area) * 100

    return result.to_dict(orient="records")

def get_soil_geojson(polygon):
    polygon = shape(polygon)

    poly_gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")

    intersection = gpd.overlay(soil_gdf, poly_gdf, how="intersection")

    return intersection.to_json()

def analyze_soil_polygon(polygon):
    distribution = get_soil_distribution(polygon)
    geojson = get_soil_geojson(polygon)

    return {
        "distribution": distribution,
        "geojson": geojson
    }   