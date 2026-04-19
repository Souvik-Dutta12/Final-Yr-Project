import express from "express";
import { Analyse } from "../controllers/farmland-controller.js";
import { validate } from "../middlewares/validate-middleware.js";
import { polygonSchema } from "../validations/farmland-validation.js";
const router = express.Router();

router.route("/analyse").post(validate(polygonSchema), Analyse);

export default router;