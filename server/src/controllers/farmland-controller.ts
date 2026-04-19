import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import type { PolygonSchema } from "../validations/farmland-validation.js";
import type { Request, Response } from "express";
import axios from "axios";

type PolygonRequest = Request<{},{}, PolygonSchema>;

const Analyse = asyncHandler(async (req:PolygonRequest, res:Response): Promise<Object> => {
  const URL = process.env.URL;
  const { polygon } = req.body;
  if (!polygon) {
    throw new ApiError(400, "Polygon is required!");
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
