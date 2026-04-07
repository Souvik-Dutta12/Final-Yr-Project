import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import axios from "axios";

const Analyse = asyncHandler(async (req, res) => {
  const URL = process.env.URL;
  const { polygon } = req.body;
  if (!polygon && !polygon.coordinates) {
    throw new ApiError(400, "Polygon coordinates are required!");
  }

  if (polygon.coordinates[0].length < 3) {
    throw new ApiError(400, "Atleast 3 coordinates are required");
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
