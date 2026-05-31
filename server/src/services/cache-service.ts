import redisClient from "../configs/radis.js";
import crypto from "crypto";

const PENDING_PREFIX = "pending:";

async function get(key: string) {
  const v = await redisClient.get(key);
  if (!v) return null;
  try {
    return JSON.parse(v);
  } catch (e) {
    return v;
  }
}

async function set(key: string, value: unknown, ttlSeconds = 60 * 60 * 24) {
  const str = typeof value === "string" ? value : JSON.stringify(value);
  if (ttlSeconds > 0) {
    await redisClient.set(key, str, { EX: ttlSeconds });
  } else {
    await redisClient.set(key, str);
  }
}

async function del(key: string) {
  await redisClient.del(key);
}

async function getPending(key: string) {
  return await redisClient.get(PENDING_PREFIX + key);
}

async function setPending(key: string, jobId: string | number, ttlSeconds = 60 * 5) {
  await redisClient.set(PENDING_PREFIX + key, String(jobId), { EX: ttlSeconds });
}

async function delPending(key: string) {
  await redisClient.del(PENDING_PREFIX + key);
}

export { get, set, del, getPending, setPending, delPending };

export function makeCacheKey(endpoint: string, payload?: unknown, params?: unknown) {
  const obj = { endpoint, payload: payload ?? null, params: params ?? null };
  const str = JSON.stringify(obj);
  return crypto.createHash("sha256").update(str).digest("hex");
}
