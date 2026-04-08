import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import * as turf from "@turf/turf";
import axios from "axios";

const Analyse = asyncHandler(async (req, res) => {
  //max. and min. area for polygon
  const MIN_AREA = 50_000; // 0.05 km²
  const MAX_AREA = 750_000_000; // 750 km²

  const URL = process.env.URL;
  const { polygon } = req.body;
  if (!polygon && !polygon.coordinates) {
    throw new ApiError(400, "Polygon coordinates are required!");
  }

  if (polygon.coordinates[0].length < 3) {
    throw new ApiError(400, "Atleast 3 coordinates are required");
  }
  //area calculation
  const areaInSquareMeters = turf.area(polygon);

  if (areaInSquareMeters < MIN_AREA) {
    throw new ApiError(400, "Polygon area too small for ML analysis");
  }

  if (areaInSquareMeters > MAX_AREA) {
    throw new ApiError(400, "Polygon area too large for ML analysis");
  }

  const response = await axios.post(
    `${URL}/farmland/analyse`,
    { polygon },
    { headers: { "Content-Type": "application/json" } },
  );
  const data = response.data.data;

  if (!data) {
    throw new ApiError(400, "Failed to analyse farmland");
  }

  return res
    .status(200)
    .json(new ApiResponse(200, data, "Farmland analysed successfully"));
});

export { Analyse };
