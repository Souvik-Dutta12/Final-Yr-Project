import dotenv from "dotenv";

dotenv.config();

const bullRedisConnection = {
  host: process.env.REDIS_HOST,
  port: Number(process.env.REDIS_PORT),
  maxRetriesPerRequest: null,
};


export default bullRedisConnection;