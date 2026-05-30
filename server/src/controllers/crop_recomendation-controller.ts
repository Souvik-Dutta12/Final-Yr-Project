import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import type { Response, Request } from "express";
import type {
  CropInsightsInput,
  CropInsightsPolygonSchema,
} from "../validations/crop-validation.js";
import addJobForEndpoint, { queueNameFromEndpoint, getJobFromQueue, waitForJobResult } from "../services/queue-service.js";
import { get, set, getPending, setPending, delPending, makeCacheKey } from "../services/cache-service.js";

type CropRequest = Request<{}, {}, CropInsightsInput>;
type CropRequestPolygon = Request<{}, {}, CropInsightsPolygonSchema>;

const cropInsights = asyncHandler(
  async (req: CropRequest, res: Response): Promise<Object> => {
    const { features } = req.body;
    console.log(`[crop] cropInsights request received features=${JSON.stringify(features).slice(0,200)}`);
    if (!features) {
      throw new ApiError(400, "Features are required!");
    }

    const endpoint = "/crops-reccomendation/crop-insights";
    const cacheKey = makeCacheKey(endpoint, { features });

    const cached = await get(cacheKey);
    if (cached) {
      console.log(`[crop] cache hit for ${cacheKey}`);
      return res.status(200).json(new ApiResponse(200, cached, "Crop insights (cached)"));
    }

    const pending = await getPending(cacheKey);
    if (pending) {
      const queueName = queueNameFromEndpoint(endpoint);
      const existingJob = await getJobFromQueue(queueName, pending);
      if (existingJob) {
        const result = await waitForJobResult(existingJob);
        await set(cacheKey, result);
        await delPending(cacheKey);
        return res.status(200).json(new ApiResponse(200, result, "Crop insights completed"));
      }
    }

    const job = await addJobForEndpoint(endpoint, "POST", { features });
    console.log(`[crop] enqueued job ${job.id} for ${cacheKey}`);
    await setPending(cacheKey, String(job.id));
    try {
      const result = await waitForJobResult(job);
      console.log(`[crop] job ${job.id} completed`);
      await set(cacheKey, result);
      await delPending(cacheKey);
      return res.status(200).json(new ApiResponse(200, result, "Crop insights completed"));
    } catch (err) {
      console.error(`[crop] job ${job.id} error:`, err);
      await delPending(cacheKey);
      throw err;
    }
  },
);

const cropInsightsPolygon = asyncHandler(
  async (req: CropRequestPolygon, res: Response): Promise<Object> => {
    const URL = process.env.URL;
    const { soil_data } = req.body;
    if (!soil_data) {
      throw new ApiError(400, "Features or Types are required!");
    }

    const endpoint = "/crops-reccomendation/crop-insights/polygon";
    const cacheKey = makeCacheKey(endpoint, { soil_data });

    const cached = await get(cacheKey);
    if (cached) return res.status(200).json(new ApiResponse(200, cached, "Crop polygon insights (cached)"));

    const pending = await getPending(cacheKey);
    if (pending) {
      const queueName = queueNameFromEndpoint(endpoint);
      const existingJob = await getJobFromQueue(queueName, pending);
      if (existingJob) {
        const result = await waitForJobResult(existingJob);
        await set(cacheKey, result);
        await delPending(cacheKey);
        return res.status(200).json(new ApiResponse(200, result, "Crop polygon insights completed"));
      }
    }

    const job2 = await addJobForEndpoint(endpoint, "POST", { soil_data });
    console.log(`[crop] enqueued job ${job2.id} for ${cacheKey}`);
    await setPending(cacheKey, String(job2.id));
    try {
      const result = await waitForJobResult(job2);
      console.log(`[crop] job ${job2.id} completed`);
      await set(cacheKey, result);
      await delPending(cacheKey);
      return res.status(200).json(new ApiResponse(200, result, "Crop polygon insights completed"));
    } catch (err) {
      console.error(`[crop] job ${job2.id} error:`, err);
      await delPending(cacheKey);
      throw err;
    }
  },
);

export { cropInsights, cropInsightsPolygon };
