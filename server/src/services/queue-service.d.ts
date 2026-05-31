import type { Method } from "axios";

declare function addJobForEndpoint(
  endpoint: string,
  method: Method,
  payload?: Record<string, unknown>,
  params?: Record<string, unknown>,
): Promise<{
  id: string | number;
}>;

export declare function waitForJobResult<T = unknown>(job: import("bullmq").Job<T>, timeoutMs?: number): Promise<T>;
export declare function getJobFromQueue(queueName: string, jobId: string | number): Promise<import("bullmq").Job | null>;
export declare function queueNameFromEndpoint(endpoint: string): string;

export default addJobForEndpoint;
