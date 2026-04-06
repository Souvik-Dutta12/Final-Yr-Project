import express from "express";
import { Analyse } from "../controllers/farmland-controller.js";
const router = express.Router();

router.route("/analyse").post(Analyse);

export default router;