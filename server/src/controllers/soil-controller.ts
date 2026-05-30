import { asyncHandler } from "../utils/asyncHandler.js";
import { ApiError } from "../utils/apiError.js";
import { ApiResponse } from "../utils/apiResponse.js";
import addJobForEndpoint, { queueNameFromEndpoint, getJobFromQueue, waitForJobResult } from "../services/queue-service.js";
import { get, set, getPending, setPending, delPending, makeCacheKey } from "../services/cache-service.js";

const LatLonSoilType = asyncHandler(async (req, res) => {
  const { lat, lon } = req.query;
  console.log(`[soil] LatLon request received - lat=${lat} lon=${lon}`);
  if (!lat || !lon) {
    throw new ApiError(400, "Latitude and Longitude required");
  }

  const job = await addJobForEndpoint("/soil/", "GET", undefined, {
    lat: String(lat),
    lon: String(lon),
  });
  // Use cache key for this request
  const cacheKey = makeCacheKey("/soil/", undefined, { lat: String(lat), lon: String(lon) });

  // Check cache
  const cached = await get(cacheKey);
  if (cached) {
    console.log(`[soil] cache hit for ${cacheKey}`);
    return res.status(200).json(new ApiResponse(200, cached, "Soil lookup (cached)"));
  }

  // If another job is pending for same key, wait for it
  const pending = await getPending(cacheKey);
  if (pending) {
    const queueName = queueNameFromEndpoint("/soil/");
    const existingJob = await getJobFromQueue(queueName, pending);
    if (existingJob) {
      console.log(`[soil] pending job found ${pending} - waiting`);
      const result = await waitForJobResult(existingJob);
      await set(cacheKey, result);
      await delPending(cacheKey);
      return res.status(200).json(new ApiResponse(200, result, "Soil lookup completed"));
    }
  }

  // No cache and no pending job -> enqueue and wait
  const job2 = job;
  console.log(`[soil] enqueued job ${job2.id} for ${cacheKey}`);
  await setPending(cacheKey, String(job2.id));
  try {
    const result = await waitForJobResult(job2);
    console.log(`[soil] job ${job2.id} completed`);
    await set(cacheKey, result);
    await delPending(cacheKey);
    return res.status(200).json(new ApiResponse(200, result, "Soil lookup completed"));
  } catch (err) {
    console.error(`[soil] job ${job2.id} error:`, err);
    await delPending(cacheKey);
    throw err;
  }
});

const PolygonSoilType = asyncHandler(async (req, res) => {
  const { polygon } = req.body;
  if (!polygon || !polygon.coordinates) {
    throw new ApiError(400, "Polygon coordinates are required!");
  }

  if (polygon.coordinates[0].length < 3) {
    throw new ApiError(400, "At least 3 coordinates are required");
  }

  const endpoint = "/soil/polygon";
  const cacheKey = makeCacheKey(endpoint, { polygon });

  const cached = await get(cacheKey);
  if (cached) return res.status(200).json(new ApiResponse(200, cached, "Soil polygon (cached)"));

  const pending = await getPending(cacheKey);
  if (pending) {
    const queueName = queueNameFromEndpoint(endpoint);
    const existingJob = await getJobFromQueue(queueName, pending);
    if (existingJob) {
      const result = await waitForJobResult(existingJob);
      await set(cacheKey, result);
      await delPending(cacheKey);
      return res.status(200).json(new ApiResponse(200, result, "Soil polygon lookup completed"));
    }
  }

  const job3 = await addJobForEndpoint(endpoint, "POST", { polygon });
  await setPending(cacheKey, String(job3.id));
  try {
    const result = await waitForJobResult(job3);
    await set(cacheKey, result);
    await delPending(cacheKey);
    return res.status(200).json(new ApiResponse(200, result, "Soil polygon lookup completed"));
  } catch (err) {
    await delPending(cacheKey);
    throw err;
  }
});

export { LatLonSoilType, PolygonSoilType };
