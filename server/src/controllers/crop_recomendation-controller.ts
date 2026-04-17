import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import axios from "axios";
import type { Response, Request } from "express";
import type {
  CropInsightsInput,
  CropInsightsPolygonSchema,
} from "../validations/crop-validation.js";

type CropRequest = Request<{}, {}, CropInsightsInput>;
type CropRequestPolygon = Request<{}, {}, CropInsightsPolygonSchema>;

const cropInsights = asyncHandler(
  async (req: CropRequest, res: Response): Promise<Object> => {
    const URL = process.env.URL;
    const { features } = req.body;
    if (!features) {
      throw new ApiError(400, "Features are required!");
    }

    const response = await axios.post(
      `${URL}/crops-reccomendation/crop-insights`,
      { features },
      { headers: { "Content-Type": "application/json" } },
    );
    const recommendedCrops = response.data.data.recommendedCrops;

    if (!recommendedCrops) {
      throw new ApiError(400, "Failed to fetch crop insights");
    }

    return res
      .status(200)
      .json(
        new ApiResponse(
          200,
          recommendedCrops,
          "Crop insights fetched successfylly!",
        ),
      );
  },
);

const cropInsightsPolygon = asyncHandler(
  async (req: CropRequestPolygon, res: Response): Promise<Object> => {
    const URL = process.env.URL;
    const { soil_data } = req.body;
    if (!soil_data) {
      throw new ApiError(400, "Features or Types are required!");
    }

    const response = await axios.post(
      `${URL}/crops-reccomendation/crop-insights/polygon`,
      { soil_data },
      { headers: { "Content-Type": "application/json" } },
    );
    const recommendedCrops = response.data.data.results;

    if (!recommendedCrops) {
      throw new ApiError(400, "Failed to fetch crop insights for polygon");
    }

    return res
      .status(200)
      .json(
        new ApiResponse(
          200,
          recommendedCrops,
          "Crop insights for polygon fetched successfylly!",
        ),
      );
  },
);

export { cropInsights, cropInsightsPolygon };
