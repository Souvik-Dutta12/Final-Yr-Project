import axios from "axios";
import type { AxiosRequestConfig, Method } from "axios";

type PythonRequestOptions = {
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  timeoutMs?: number;
  responseType?: AxiosRequestConfig["responseType"];
};

const callPythonServer = async <T = unknown>(
  endpoint: string,
  method: Method,
  payload?: Record<string, unknown>,
  options: PythonRequestOptions = {},
): Promise<T> => {
  const baseUrl = process.env.URL;
  if (!baseUrl) {
    throw new Error(" URL environment variable is not set");
  }

  const url = `${baseUrl.replace(/\/+$/, "")}/${endpoint.replace(/^\/+/, "")}`;

  const config: AxiosRequestConfig = {
    method,
    url,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    params: options.params,
    timeout: options.timeoutMs ?? 300000,
    responseType: options.responseType ?? "json",
  };

  if (payload !== undefined && payload !== null) {
    if (method?.toString().toUpperCase() === "GET" || method?.toString().toUpperCase() === "DELETE") {
      config.params = {
        ...config.params,
        ...payload,
      };
    } else {
      config.data = payload;
    }
  }

  const response = await axios.request<T>(config);
  return response.data;
};

export { callPythonServer };
