import express from "express";
import { cropInsights, cropInsightsPolygon } from "../controllers/crop_recomendation-controller.js";
import { cropInsightsSchema, cropInsightsPolygonSchema } from "../validations/crop-validation.js";
import { validate } from "../middlewares/validate-middleware.js";

const router = express.Router();

router.route("/").post(validate(cropInsightsSchema), cropInsights);
router.route("/polygon").post(validate(cropInsightsPolygonSchema), cropInsightsPolygon)

export default router;