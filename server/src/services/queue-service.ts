import { Queue, Worker, Job, QueueEvents } from "bullmq";
import type { Method } from "axios";
import bullRedisConnection from "../configs/ioredis.js";
import { callPythonServer } from "./python-service.js";

const queues = new Map<string, Queue>();
const workers = new Map<string, Worker>();
const queueEvents = new Map<string, QueueEvents>();

export function queueNameFromEndpoint(endpoint: string) {
  // endpoint: /crops-reccomendation/crop-insights -> crops-reccomendation
  const parts = endpoint.replace(/^\/+/, "").split("/");
  return parts[0] || "python-default";
}

function createQueueAndWorker(name: string) {
  if (queues.has(name)) return queues.get(name)!;

  const connectionOptions = bullRedisConnection;

  const q = new Queue(name, {
    connection: connectionOptions,
    defaultJobOptions: {
      attempts: 3,
      backoff: { type: "exponential", delay: 2000 },
      removeOnComplete: 100,
      removeOnFail: 50,
    },
  });

  queues.set(name, q);

  // Create a worker with concurrency 1 so only one job for this endpoint runs at a time
  const w = new Worker(
    name,
    async (job: Job<any>) => {
      const { endpoint, method, payload, params } = job.data;
      return await callPythonServer(endpoint, method as Method, payload, { params });
    },
    {
      connection: connectionOptions,
      concurrency: 1,
    },
  );

  w.on("completed", (job) => {
    console.log(`Job ${job.id} completed on queue ${name}`);
  });

  w.on("failed", (job, err) => {
    console.error(`Job ${job?.id} failed on queue ${name}:`, err?.message || err);
  });

  workers.set(name, w);
  return q;
}

function createQueueEvents(name: string) {
  if (queueEvents.has(name)) return queueEvents.get(name)!;

  const events = new QueueEvents(name, {
    connection: bullRedisConnection,
  });

  events.on("error", (error) => {
    console.error(`QueueEvents error for queue ${name}:`, error?.message || error);
  });

  queueEvents.set(name, events);
  return events;
}

export async function waitForJobResult<T = unknown>(job: Job<T>, timeoutMs = 300_000) {
  const events = createQueueEvents(job.queueName);
  await events.waitUntilReady();
  return job.waitUntilFinished(events, timeoutMs);
}

async function addJobForEndpoint(
  endpoint: string,
  method: Method,
  payload?: Record<string, unknown>,
  params?: Record<string, unknown>,
) {
  const name = queueNameFromEndpoint(endpoint);
  const q = createQueueAndWorker(name);

  const job = await q.add(name + "-job", {
    endpoint,
    method,
    payload,
    params,
  });

  return job;
}

export async function getJobFromQueue(queueName: string, jobId: string | number) {
  const q = createQueueAndWorker(queueName);
  // Queue.getJob exists in BullMQ
  // @ts-ignore
  return q.getJob(jobId as any);
}

export default addJobForEndpoint;
