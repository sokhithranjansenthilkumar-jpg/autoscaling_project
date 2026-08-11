import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

const http = axios.create({
  baseURL: API_BASE,
  timeout: 8000,
});

export function getApiBase() {
  return API_BASE;
}

export async function getHealth() {
  const response = await http.get("/health/");
  return response.data;
}

export async function getDataset() {
  const response = await http.get("/dataset/");
  return response.data;
}

export async function getMarketplaceStatus() {
  const response = await http.get("/status/marketplaces/");
  return response.data;
}

export async function predict(users, cpu, memory, latency) {
  const response = await http.post("/predict/", { users, cpu, memory, latency });
  return response.data;
}

export async function publishMarketplaceMetric(
  source,
  users,
  cpu,
  memory,
  latency,
  instances
) {
  const response = await http.post("/predict/marketplace/", {
    source,
    users,
    cpu,
    memory,
    latency,
    instances,
  });
  return response.data;
}
