import { RateLimiterRedis } from "rate-limiter-flexible";
import { Redis } from "ioredis";
import type { Request, Response, NextFunction } from "express";

const rateLimiterRedisClient = new Redis({
  host: process.env.REDIS_HOST,
  port: Number(process.env.REDIS_PORT),
  maxRetriesPerRequest: null,
});

interface LimiterOptions {
  points: number;
  duration: number;
  blockDuration?: number;
  keyPrefix: string;
}

export const createRateLimiter = ({
  points,
  duration,
  blockDuration = 0,
  keyPrefix,
}: LimiterOptions) => {
  const limiter = new RateLimiterRedis({
    storeClient: rateLimiterRedisClient,
    points,
    duration,
    blockDuration,
    keyPrefix,
  });

  return async (req: Request, res: Response, next: NextFunction) => {
    const ip =
      req.ip ||
      String(req.headers["x-forwarded-for"] || req.socket.remoteAddress || "unknown");

    try {
      await limiter.consume(ip);
      next();
    } catch (error: any) {
      console.error("Rate limiter caught error", { ip, error });
      if (error?.msBeforeNext !== undefined) {
        return res.status(429).json({
          success: false,
          message: "Too many requests",
          retryAfter: Math.ceil(error.msBeforeNext / 1000),
        });
      }

      return res.status(500).json({
        success: false,
        message: "Rate limiter failure",
        error: error?.message ?? String(error),
      });
    }
  };
};