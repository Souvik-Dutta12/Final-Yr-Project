import type { ZodSchema } from "zod";
import type { Request, Response, NextFunction } from "express";
import { ApiError } from "../utils/apiError.js";

export const validate =
  <T>(schema: ZodSchema<T>) =>
  (req: Request<any, any, T>, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body);

    if (!result.success) {
      return next(new ApiError(400,"Validation error",result.error.issues));
    }

    req.body = result.data;
    next();
  };