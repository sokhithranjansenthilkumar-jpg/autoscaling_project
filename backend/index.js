const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");

dotenv.config();

const DEFAULTS = {
  port: 5000,
  djangoApi: "http://127.0.0.1:8000",
  frontendUrl: "http://127.0.0.1:3000",
  requestTimeoutMs: 4000,
};

function toInteger(value, fallbackValue) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackValue;
}

function sanitizeUrl(value, fallbackValue) {
  const raw = String(value || fallbackValue).trim();
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

function buildConfig() {
  return {
    serviceName: "autoscaling-node-helper",
    port: toInteger(process.env.PORT, DEFAULTS.port),
    djangoApi: sanitizeUrl(process.env.DJANGO_API, DEFAULTS.djangoApi),
    frontendUrl: sanitizeUrl(process.env.FRONTEND_URL, DEFAULTS.frontendUrl),
    requestTimeoutMs: toInteger(
      process.env.REQUEST_TIMEOUT_MS,
      DEFAULTS.requestTimeoutMs
    ),
  };
}

const config = buildConfig();
const app = express();
app.use(cors());
app.use(express.json({ limit: "256kb" }));

function serviceUrls() {
  return {
    dashboard: config.frontendUrl,
    django_api: config.djangoApi,
    node_helper: `http://127.0.0.1:${config.port}`,
  };
}

async function getJson(pathname) {
  const response = await fetch(`${config.djangoApi}${pathname}`, {
    signal: AbortSignal.timeout(config.requestTimeoutMs),
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Upstream ${pathname} failed with status ${response.status}`);
  }

  return response.json();
}

function sendGatewayError(res, details) {
  res.status(503).json({
    ok: false,
    service: config.serviceName,
    error: "Django upstream is unavailable",
    details,
    services: serviceUrls(),
    time: new Date().toISOString(),
  });
}

app.get("/", (req, res) => {
  res.json({
    ok: true,
    service: config.serviceName,
    status: "running",
    message: "Node helper is online. Use Django for ML APIs and React for UI.",
    services: serviceUrls(),
    routes: ["/health", "/services"],
    time: new Date().toISOString(),
  });
});

app.get("/health", async (req, res) => {
  try {
    const djangoHealth = await getJson("/health/");
    res.json({
      ok: true,
      service: config.serviceName,
      node: {
        ok: true,
        port: config.port,
      },
      django: djangoHealth,
      services: serviceUrls(),
      time: new Date().toISOString(),
    });
  } catch (error) {
    sendGatewayError(res, error.message);
  }
});

app.get("/services", async (req, res) => {
  try {
    const [health, dataset] = await Promise.all([
      getJson("/health/"),
      getJson("/dataset/"),
    ]);

    res.json({
      ok: true,
      summary: "Autoscaling stack overview",
      services: serviceUrls(),
      dataset: {
        count: dataset.count,
        cpu_range: [dataset.cpuMin, dataset.cpuMax],
        instance_range: [dataset.instanceMin, dataset.instanceMax],
      },
      django_health: health,
      time: new Date().toISOString(),
    });
  } catch (error) {
    sendGatewayError(res, error.message);
  }
});

app.use((req, res) => {
  res.status(404).json({
    ok: false,
    error: "Route not found",
    route: req.originalUrl,
    available_routes: ["/", "/health", "/services"],
  });
});

app.listen(config.port, () => {
  console.log(`Node helper running on http://127.0.0.1:${config.port}`);
  console.log(`Django API expected at ${config.djangoApi}`);
  console.log(`Frontend expected at ${config.frontendUrl}`);
  console.log(`Request timeout: ${config.requestTimeoutMs}ms`);
});
