import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import type { PolygonSchema } from "../validations/farmland-validation.js";
import type { Request, Response } from "express";
import addJobForEndpoint, { queueNameFromEndpoint, getJobFromQueue, waitForJobResult } from "../services/queue-service.js";
import { get, set, getPending, setPending, delPending, makeCacheKey } from "../services/cache-service.js";

type PolygonRequest = Request<{}, {}, PolygonSchema>;

const Analyse = asyncHandler(async (req: PolygonRequest, res: Response): Promise<Object> => {
  const { polygon } = req.body;
  console.log(`[farmland] Analyse request received`);
  if (!polygon) {
    throw new ApiError(400, "Polygon is required!");
  }

  const endpoint = "/analyse";
  const cacheKey = makeCacheKey(endpoint, { polygon });

  const cached = await get(cacheKey);
  if (cached) {
    console.log(`[farmland] cache hit for ${cacheKey}`);
    return res.status(200).json(new ApiResponse(200, cached, "Farmland analyse (cached)"));
  }

  const pending = await getPending(cacheKey);
  if (pending) {
    const queueName = queueNameFromEndpoint(endpoint);
    const existingJob = await getJobFromQueue(queueName, pending);
    if (existingJob) {
      console.log(`[farmland] pending job ${pending} found - waiting`);
      const result = await waitForJobResult(existingJob);
      await set(cacheKey, result);
      await delPending(cacheKey);
      return res.status(200).json(new ApiResponse(200, result, "Farmland analyse completed"));
    }
  }

  const job = await addJobForEndpoint(endpoint, "POST", { polygon });
  console.log(`[farmland] enqueued job ${job.id} for ${cacheKey}`);
  await setPending(cacheKey, String(job.id));
  try {
    const result = await waitForJobResult(job);
    console.log(`[farmland] job ${job.id} completed`);
    await set(cacheKey, result);
    await delPending(cacheKey);
    return res.status(200).json(new ApiResponse(200, result, "Farmland analyse completed"));
  } catch (err) {
    console.error(`[farmland] job ${job.id} error:`, err);
    await delPending(cacheKey);
    throw err;
  }
});

export { Analyse };
