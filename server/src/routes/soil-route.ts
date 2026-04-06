import express from "express";
import { LatLonSoilType,PolygonSoilType } from "../controllers/soil-controller.js";
const router = express.Router();

router.route("/point").get(LatLonSoilType);
router.route("/polygon").post(PolygonSoilType);

export default router;