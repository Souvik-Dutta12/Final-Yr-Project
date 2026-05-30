import express from "express";
import { LatLonSoilType,PolygonSoilType } from "../controllers/soil-controller.js";
import { createRateLimiter } from "../middlewares/rate-limiter.js";
const router = express.Router();

const Limiter = createRateLimiter({
  points: 10,
  duration: 60,
  blockDuration: 30,
  keyPrefix: "soil_type",
});

router.route("/point").get(Limiter,LatLonSoilType);
router.route("/polygon").post(Limiter,PolygonSoilType);

export default router;