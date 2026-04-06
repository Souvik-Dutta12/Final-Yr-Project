import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import axios from "axios";

const LatLonSoilType = asyncHandler(async (req, res) => {
  const URL = process.env.URL;
  const { lat, lon } = req.query;
  if (!lat || !lon) {
    throw new ApiError(400, "Latitude and Longitude required");
  }

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });

  const response = await axios.get(`${URL}/soil/?${params.toString()}`);
  const data = response.data.data;

  if (!data) {
    throw new ApiError(400, "Failed to fetch soil type");
  }

  return res
    .status(200)
    .json(new ApiResponse(200, data, "Soil type for point fetched"));
});

const PolygonSoilType = asyncHandler(async (req, res) => {
  const URL = process.env.URL;
  const { polygon } = req.body;
  if (!polygon && !polygon.coordinates) {
    throw new ApiError(400, "Polygon coordinates are required!");
  }

  if (polygon.coordinates[0].length < 3) {
    throw new ApiError(400, "Atleast 3 coordinates are required");
  }

  const response = await axios.post(
    `${URL}/soil/polygon`,
    { polygon },
    { headers: { "Content-Type": "application/json" } },
  );
  const data = response.data.data;

  if (!data) {
    throw new ApiError(400, "Failed to fetch soil type");
  }

  return res
    .status(200)
    .json(new ApiResponse(200, data, "Soil type for polygon fetched"));
});

export { LatLonSoilType, PolygonSoilType };
