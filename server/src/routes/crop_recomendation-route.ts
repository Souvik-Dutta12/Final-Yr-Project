import express from "express";
import { cropInsights, cropInsightsPolygon } from "../controllers/crop_recomendation-controller.js";
import { cropInsightsSchema, cropInsightsPolygonSchema } from "../validations/crop-validation.js";
import { validate } from "../middlewares/validate-middleware.js";
import { createRateLimiter } from "../middlewares/rate-limiter.js";

const router = express.Router();

const Limiter = createRateLimiter({
  points: 5,
  duration: 60,
  blockDuration: 120,
  keyPrefix: "crop_insights",
});

router.route("/").post(Limiter, validate(cropInsightsSchema), cropInsights);
router.route("/polygon").post(Limiter, validate(cropInsightsPolygonSchema), cropInsightsPolygon)

export default router;