import { ApiError } from "../utils/apiError.js";
import type { Request, Response, NextFunction} from "express";

const errorMiddleware = (err:Error, req: Request, res:Response, next: NextFunction) => {
  if (err instanceof ApiError) {
    return res.status(err.statusCode).json({
      success: false,
      message: err.message,
      errors: err.error || []
    });
  }
  return res.status(500).json({
    success: false,
    message: err.message || "Internal Server Error"
  });
};

export{
  errorMiddleware
};
