import express from "express";
import { Analyse } from "../controllers/farmland-controller.js";
import { validate } from "../middlewares/validate-middleware.js";
import { polygonSchema } from "../validations/farmland-validation.js";
import { createRateLimiter } from "../middlewares/rate-limiter.js";
const router = express.Router();

const Limiter = createRateLimiter({
  points: 5,
  duration: 60,
  blockDuration: 120,
  keyPrefix: "polygon_analyse",
});

router.route("/analyse").post(Limiter,validate(polygonSchema), Analyse);

export default router;