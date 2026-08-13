import React, { useCallback, useEffect, useMemo, useState } from "react";
import CpuInstanceChart from "./CpuInstanceChart";
import {
  getApiBase,
  getDataset,
  getHealth,
  getMarketplaceStatus,
  predict,
  publishMarketplaceMetric,
} from "../api";

const FALLBACK_DATASET_POINTS = [
  { cpu: 10, instances: 1 },
  { cpu: 20, instances: 1 },
  { cpu: 30, instances: 1 },
  { cpu: 40, instances: 1 },
  { cpu: 50, instances: 2 },
  { cpu: 60, instances: 2 },
  { cpu: 70, instances: 2 },
  { cpu: 80, instances: 3 },
  { cpu: 90, instances: 3 },
  { cpu: 95, instances: 4 },
];

const INITIAL_FORM = {
  users: "200",
  cpu: "74",
  memory: "68",
  latency: "165",
};

const INITIAL_INPUT_SETS = [
  { ...INITIAL_FORM },
  { users: "260", cpu: "55", memory: "60", latency: "124" },
  { users: "420", cpu: "74", memory: "68", latency: "165" },
  { users: "610", cpu: "84", memory: "79", latency: "218" },
  { users: "920", cpu: "95", memory: "91", latency: "332" },
];

const MARKETPLACE_BASE_INSTANCES = {
  amazon: 4,
  flipkart: 2,
  meesho: 2,
  ajio: 4,
  myntra: 5,
};

function normalizeInputs(values) {
  return {
    users: Number(values.users),
    cpu: Number(values.cpu),
    memory: Number(values.memory),
    latency: Number(values.latency),
  };
}

function resolveMarketplaceInstances(source) {
  return MARKETPLACE_BASE_INSTANCES[source] || 1;
}

function PredictForm() {
  const [inputSets, setInputSets] = useState(INITIAL_INPUT_SETS);
  const [results, setResults] = useState([]);
  const [activeInputIndex, setActiveInputIndex] = useState(null);
  const [datasetPoints, setDatasetPoints] = useState(FALLBACK_DATASET_POINTS);
  const [datasetMeta, setDatasetMeta] = useState({
    count: FALLBACK_DATASET_POINTS.length,
    cpuMin: 10,
    cpuMax: 95,
    instanceMin: 1,
    instanceMax: 4,
    source: "fallback",
  });
  const [loading, setLoading] = useState(false);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [isRealtime, setIsRealtime] = useState(false);
  const [intervalMs, setIntervalMs] = useState(2000);
  const [lastUpdated, setLastUpdated] = useState("");
  const [error, setError] = useState("");
  const [datasetError, setDatasetError] = useState("");
  const [marketStatus, setMarketStatus] = useState({});
  const [marketplaceError, setMarketplaceError] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [autoPublish, setAutoPublish] = useState(true);
  const [backendHealth, setBackendHealth] = useState({
    ok: false,
    time: "",
    loading: true,
  });

  const API_BASE = getApiBase();
  const canPredict = inputSets.every((set) =>
    Object.values(set).every((value) => value !== "")
  );
  const marketSources = useMemo(
    () => ["amazon", "flipkart", "meesho", "ajio", "myntra"],
    []
  );
  const inputSetMarketSources = useMemo(
    () => ["amazon", "flipkart", "meesho", "ajio", "myntra"],
    []
  );
  const connectedMarkets = marketSources.filter((source) => marketStatus[source]).length;
  const primaryResult = results[0] || null;
  const latestRecommendation = primaryResult ? `${primaryResult.instances} nodes` : "Waiting";
  const datasetRange =
    datasetMeta.cpuMin != null && datasetMeta.cpuMax != null
      ? `${datasetMeta.cpuMin}% to ${datasetMeta.cpuMax}%`
      : "Unavailable";

  const intervalOptions = useMemo(
    () => [
      { label: "1 second", value: 1000 },
      { label: "2 seconds", value: 2000 },
      { label: "5 seconds", value: 5000 },
    ],
    []
  );

  const refreshHealth = useCallback(async () => {
    try {
      const response = await getHealth();
      setBackendHealth({
        ok: Boolean(response.ok),
        time: response.time || "",
        loading: false,
      });
    } catch (err) {
      setBackendHealth({
        ok: false,
        time: "",
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  useEffect(() => {
    const loadDataset = async () => {
      setDatasetLoading(true);
      try {
        const response = await getDataset();
        const points = response.points || [];
        const nextPoints =
          points.length > 0 ? points : FALLBACK_DATASET_POINTS;

        setDatasetPoints(nextPoints);
        setDatasetMeta({
          count: response.count ?? nextPoints.length,
          cpuMin: response.cpuMin ?? nextPoints[0].cpu,
          cpuMax:
            response.cpuMax ??
            nextPoints[nextPoints.length - 1].cpu,
          instanceMin: response.instanceMin ?? 1,
          instanceMax: response.instanceMax ?? 4,
          source: points.length > 0 ? "backend" : "fallback",
        });
        setDatasetError("");
      } catch (err) {
        setDatasetPoints(FALLBACK_DATASET_POINTS);
        setDatasetMeta({
          count: FALLBACK_DATASET_POINTS.length,
          cpuMin: 10,
          cpuMax: 95,
          instanceMin: 1,
          instanceMax: 4,
          source: "fallback",
        });
        setDatasetError(
          err?.response?.data?.error ||
            "Dataset API was unavailable, so fallback chart data is being shown."
        );
      } finally {
        setDatasetLoading(false);
      }
    };

    loadDataset();
  }, []);

  const fetchMarketplaceStatus = useCallback(async () => {
    try {
      const response = await getMarketplaceStatus();
      setMarketStatus(response.status || {});
      setMarketplaceError("");
    } catch (err) {
      setMarketplaceError(
        err?.response?.data?.error || "Failed to load marketplace status."
      );
    }
  }, []);

  useEffect(() => {
    fetchMarketplaceStatus();
    const timer = setInterval(fetchMarketplaceStatus, 3000);
    return () => clearInterval(timer);
  }, [fetchMarketplaceStatus]);

  const resolveCurrentInstances = useCallback(
    (source, fallback = 1) => {
      const knownValue = Number(marketStatus?.[source]?.snapshot?.instances);
      if (Number.isFinite(knownValue) && knownValue > 0) {
        return Math.trunc(knownValue);
      }

      const recommendedValue = Number(
        marketStatus?.[source]?.recommended_instances
      );
      if (Number.isFinite(recommendedValue) && recommendedValue > 0) {
        return Math.trunc(recommendedValue);
      }
      return fallback;
    },
    [marketStatus]
  );

  const publishMetric = useCallback(
    async (source, inputValues = null, instanceCountOverride) => {
      const overrideValue = Number(instanceCountOverride);
      const nextCurrentInstances =
        Number.isFinite(overrideValue) && overrideValue > 0
          ? Math.trunc(overrideValue)
          : resolveCurrentInstances(source, 1);

      const selectedInput = inputValues || inputSets[0];
      await publishMarketplaceMetric(
        source,
        Number(selectedInput.users),
        Number(selectedInput.cpu),
        Number(selectedInput.memory),
        Number(selectedInput.latency),
        nextCurrentInstances
      );
    },
    [inputSets, resolveCurrentInstances]
  );

  const runPrediction = useCallback(async (inputOverride = null) => {
    const nextSets = inputOverride || inputSets;
    const nextCanPredict = nextSets.every((set) =>
      Object.values(set).every((value) => value !== "")
    );

    if (!nextCanPredict) {
      setError("Complete every input set first.");
      return;
    }

    try {
      setError("");
      setLoading(true);
      setActiveInputIndex(null);
      const normalizedSets = nextSets.map((set) => normalizeInputs(set));
      const responses = await Promise.all(
        normalizedSets.map((set) =>
          predict(set.users, set.cpu, set.memory, set.latency)
        )
      );

      setResults(
        responses.map((response, index) => ({
          ...response,
          inputIndex: index + 1,
          requestedUsers: normalizedSets[index].users,
          requestedCpu: normalizedSets[index].cpu,
          requestedMemory: normalizedSets[index].memory,
          requestedLatency: normalizedSets[index].latency,
          calculatedAt: new Date().toLocaleTimeString(),
        }))
      );
      setLastUpdated(new Date().toLocaleTimeString());

      if (autoPublish) {
        try {
          setPublishing(true);
          await Promise.all(
            normalizedSets
              .slice(0, inputSetMarketSources.length)
              .map((set, index) => {
                const source = inputSetMarketSources[index];
                return (
                publishMarketplaceMetric(
                  source,
                  set.users,
                  set.cpu,
                  set.memory,
                  set.latency,
                  resolveCurrentInstances(source, resolveMarketplaceInstances(source))
                )
                );
              })
          );
          await fetchMarketplaceStatus();
          setMarketplaceError("");
        } catch (publishErr) {
          setMarketplaceError(
            publishErr?.response?.data?.error ||
              "Prediction worked, but auto-publish to marketplace failed."
          );
        }
      }
    } catch (err) {
      setError(err?.response?.data?.error || "Prediction failed.");
      setResults([]);
    } finally {
      setPublishing(false);
      setLoading(false);
    }
  }, [
    autoPublish,
    fetchMarketplaceStatus,
    inputSets,
    inputSetMarketSources,
  ]);

  const publishMarketplace = useCallback(
    async (source) => {
      const sourceInputIndex = inputSetMarketSources.indexOf(source);
      const selectedInput =
        sourceInputIndex >= 0 ? inputSets[sourceInputIndex] : inputSets[0];
      const isComplete = selectedInput
        ? Object.values(selectedInput).every((value) => value !== "")
        : false;

      if (!isComplete) {
        setError(
          sourceInputIndex >= 0
            ? `Complete input set ${sourceInputIndex + 1} first.`
            : "Complete the required prediction inputs first."
        );
        return;
      }

      try {
        setPublishing(true);
        const normalizedInput = normalizeInputs(selectedInput);
        const predictedVal = results.find(r => r && r.inputIndex === sourceInputIndex + 1)?.instances;
        const instancesToSend = (predictedVal != null)
          ? predictedVal
          : resolveMarketplaceInstances(source);
        await publishMetric(
          source,
          normalizedInput,
          instancesToSend
        );
        await fetchMarketplaceStatus();
      } catch (err) {
        setMarketplaceError(
          err?.response?.data?.error || `Failed to publish ${source} data.`
        );
      } finally {
        setPublishing(false);
      }
    },
    [fetchMarketplaceStatus, inputSetMarketSources, inputSets, publishMetric, results]
  );

  useEffect(() => {
    if (!isRealtime || !canPredict) {
      return undefined;
    }

    runPrediction();
    const timer = setInterval(runPrediction, intervalMs);
    return () => clearInterval(timer);
  }, [canPredict, intervalMs, isRealtime, runPrediction]);

  const runSinglePrediction = useCallback(
    async (index) => {
      const targetSet = inputSets[index];
      const isComplete = Object.values(targetSet).every((value) => value !== "");
      const targetSource = inputSetMarketSources[index];

      if (!isComplete) {
        setError(`Complete input set ${index + 1} first.`);
        return;
      }

      try {
        setError("");
        setLoading(true);
        setActiveInputIndex(index);

        const normalized = normalizeInputs(targetSet);
        const response = await predict(
          normalized.users,
          normalized.cpu,
          normalized.memory,
          normalized.latency
        );

        setResults((current) => {
          const nextResults = Array(5).fill(null);
          current.forEach((r) => {
            if (r && r.inputIndex) {
              nextResults[r.inputIndex - 1] = r;
            }
          });
          nextResults[index] = {
            ...response,
            inputIndex: index + 1,
            requestedUsers: normalized.users,
            requestedCpu: normalized.cpu,
            requestedMemory: normalized.memory,
            requestedLatency: normalized.latency,
            calculatedAt: new Date().toLocaleTimeString(),
          };
          return nextResults;
        });
        setLastUpdated(new Date().toLocaleTimeString());

        if (autoPublish && targetSource) {
          try {
            setPublishing(true);
            await publishMetric(
              targetSource,
              normalized
            );
            await fetchMarketplaceStatus();
            setMarketplaceError("");
          } catch (publishErr) {
            setMarketplaceError(
              publishErr?.response?.data?.error ||
                `Prediction worked, but auto-publish failed for ${targetSource}.`
            );
          } finally {
            setPublishing(false);
          }
        }
      } catch (err) {
        setError(err?.response?.data?.error || `Prediction failed for input set ${index + 1}.`);
      } finally {
        setLoading(false);
        setActiveInputIndex(null);
      }
    },
    [autoPublish, fetchMarketplaceStatus, inputSetMarketSources, inputSets, publishMetric]
  );

  const updateInputSet = useCallback((index, field, value) => {
    setInputSets((current) =>
      current.map((set, setIndex) =>
        setIndex === index ? { ...set, [field]: value } : set
      )
    );
  }, []);

  const healthLabel = backendHealth.loading
    ? "Checking backend..."
    : backendHealth.ok
      ? "Backend connected"
      : "Backend unavailable";

  return (
    <div className="dashboard-card">
      <div className="status-strip">
        <div className={`status-pill ${backendHealth.ok ? "online" : "offline"}`}>
          <span className="status-dot" />
          {healthLabel}
        </div>
        <div className="status-copy">
          API base: <strong>{API_BASE}</strong>
          {backendHealth.time ? ` | ${backendHealth.time}` : ""}
        </div>
      </div>


      <div className="summary-grid">
        <div className="summary-card">
          <div className="summary-label">Dataset Coverage</div>
          <div className="summary-value">{datasetMeta.count}</div>
          <div className="summary-copy">
            CPU range {datasetRange}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Latest Recommendation</div>
          <div className="summary-value">{latestRecommendation}</div>
          <div className="summary-copy">
            {primaryResult ? primaryResult.action : "Run predictions to see target capacity"}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Realtime Engine</div>
          <div className="summary-value">{isRealtime ? "Active" : "Idle"}</div>
          <div className="summary-copy">
            Interval {intervalMs / 1000}s | Auto-publish {autoPublish ? "on" : "off"}
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Marketplaces Connected</div>
          <div className="summary-value">{connectedMarkets}</div>
          <div className="summary-copy">
            {connectedMarkets > 0
              ? "Live marketplace records available"
              : "Waiting for marketplace data"}
          </div>
        </div>
      </div>

      <section className="workspace-grid">
        <div className="command-panel">
          <div className="section-title-row">
            <h2 className="section-title">Prediction Inputs</h2>
            <span className="section-copy">Tune the model inputs and publish live metrics.</span>
          </div>

          <form className="predict-form">
            <div className="input-sets-grid">
              {inputSets.map((set, index) => (
                <div key={`prediction-set-${index + 1}`} className="input-set-card">
                  <div className="input-set-title">
                    Input Set {index + 1}
                    {inputSetMarketSources[index]
                      ? ` -> ${inputSetMarketSources[index].toUpperCase()}`
                      : ""}
                  </div>
                  <label className="field">
                    <span>Active Users</span>
                    <input
                      type="number"
                      min="0"
                      placeholder="e.g. 200"
                      value={set.users}
                      onChange={(event) => updateInputSet(index, "users", event.target.value)}
                      required
                    />
                  </label>

                  <label className="field">
                    <span>CPU Usage (%)</span>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      placeholder="e.g. 74"
                      value={set.cpu}
                      onChange={(event) => updateInputSet(index, "cpu", event.target.value)}
                      required
                    />
                  </label>

                  <label className="field">
                    <span>Memory Usage (%)</span>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      placeholder="e.g. 68"
                      value={set.memory}
                      onChange={(event) => updateInputSet(index, "memory", event.target.value)}
                      required
                    />
                  </label>

                  <label className="field">
                    <span>Latency (ms)</span>
                    <input
                      type="number"
                      min="1"
                      placeholder="e.g. 165"
                      value={set.latency}
                      onChange={(event) => updateInputSet(index, "latency", event.target.value)}
                      required
                    />
                  </label>

                  <button
                    type="button"
                    className="predict-btn input-set-btn"
                    disabled={loading}
                    onClick={() => runSinglePrediction(index)}
                  >
                    {loading && activeInputIndex === index ? (
                      <>
                        <span className="spinner" />
                        Predicting
                      </>
                    ) : (
                      `Run ${inputSetMarketSources[index] || `Prediction ${index + 1}`}`
                    )}
                  </button>
                </div>
              ))}
            </div>
          </form>

          <div className="realtime-controls">
            <button
              type="button"
              className={`realtime-btn ${isRealtime ? "active" : ""}`}
              onClick={() => setIsRealtime((previous) => !previous)}
              disabled={!canPredict}
            >
              {isRealtime ? "Stop Realtime" : "Start Realtime"}
            </button>
            <label className="interval-wrap">
              <span>Interval</span>
              <select
                value={intervalMs}
                onChange={(event) => setIntervalMs(Number(event.target.value))}
                disabled={isRealtime || !canPredict}
              >
                {intervalOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="auto-publish-wrap">
              <input
                type="checkbox"
                checked={autoPublish}
                onChange={(event) => setAutoPublish(event.target.checked)}
              />
              Auto-publish only the matching marketplace
            </label>
          </div>

          {isRealtime && canPredict && (
            <div className="live-status">
              Realtime mode is running. Last update: {lastUpdated || "pending..."}
            </div>
          )}

          {error && <div className="error-box">{error}</div>}
          {datasetError && <div className="notice-box">{datasetError}</div>}
        </div>

        <div className="insight-panel">
          <div className="section-title-row">
            <h2 className="section-title">Live Marketplace Status</h2>
            <span className="section-copy">Track active marketplace load and scaling decisions in one view.</span>
          </div>
          {marketplaceError && <div className="error-box">{marketplaceError}</div>}
          <div className="market-status-grid">
            {marketSources.map((source) => {
              const item = marketStatus[source];
              return (
                <div key={source} className="market-card">
                  <h4>{source.toUpperCase()}</h4>
                  {item ? (
                    <>
                      <p>Active Users: {item.snapshot.users}</p>
                      <p>CPU Usage: {item.snapshot.cpu}%</p>
                      <p>Memory Usage: {item.snapshot.memory}%</p>
                      <p>Latency: {item.snapshot.latency} ms</p>
                      <p>Current Instances: {item.snapshot.instances ?? 0}</p>
                      <p>Recommended Instances: {item.recommended_instances}</p>
                      <p className={`scale-${item.scaling}`}>
                        Status: {item.scaling.replace("_", " ")}
                      </p>
                    </>
                  ) : (
                    <p>No live data yet.</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <div className="market-status-shell">
        <div className="section-head">
          <div className="chart-title">Executive Output</div>
          <div className="chart-meta">High-level tiles with essential scaling details.</div>
        </div>
        {results.filter(Boolean).length > 0 ? (
          <div className="result-box">
            <div className="result-tag">Recommended Outputs</div>
            <h3>Prediction results by input set</h3>
            <div className="result-grid">
              {results.filter(Boolean).map((result) => {
                const source = inputSetMarketSources[result.inputIndex - 1];
                const currentInstances = source ? marketStatus[source]?.snapshot?.instances : null;
                const currentVal = currentInstances != null ? Number(currentInstances) : null;

                let stateClass = "steady";
                let scalingLabel = "Stable";

                if (currentVal != null) {
                  const delta = result.instances - currentVal;
                  if (delta > 0) {
                    stateClass = "up";
                    scalingLabel = "Scale Up";
                  } else if (delta < 0) {
                    stateClass = "down";
                    scalingLabel = "Scale Down";
                  } else {
                    stateClass = "steady";
                    scalingLabel = "Stable";
                  }
                } else {
                  if (result.instances > 2) {
                    stateClass = "up";
                    scalingLabel = "Scale Up";
                  } else if (result.instances === 2) {
                    stateClass = "steady";
                    scalingLabel = "Stable";
                  } else {
                    stateClass = "down";
                    scalingLabel = "Scale Down";
                  }
                }

                return (
                  <div key={`result-${result.inputIndex}`} className="result-set-card">
                    <div className="result-set-head">
                      <span className="result-label">
                        Input Set {result.inputIndex}
                        {source ? ` -> ${source.toUpperCase()}` : ""}
                      </span>
                      <div className={`result-state state-${stateClass}`}>
                        {scalingLabel}
                      </div>
                    </div>
                    <strong className="result-action">{result.action}</strong>
                    <span className="result-meta">Users: {result.requestedUsers}</span>
                    <span className="result-meta">CPU: {result.requestedCpu}%</span>
                    <span className="result-meta">Memory: {result.requestedMemory}%</span>
                    <span className="result-meta">Latency: {result.requestedLatency} ms</span>
                    <span className="result-meta">Current Instances: {currentVal != null ? currentVal : "N/A"}</span>
                    <span className="result-meta">Recommended: {result.instances} instance(s)</span>
                    <span className="result-meta">Updated: {result.calculatedAt}</span>
                  </div>
                );
              })}
            </div>
            <div className="marketplace-actions">
              {marketSources.map((source) => (
                <button
                  key={source}
                  type="button"
                  className="market-btn"
                  disabled={publishing}
                  onClick={() => publishMarketplace(source)}
                >
                  Send to {source.charAt(0).toUpperCase() + source.slice(1)}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="result-box result-box-empty">
            <div className="result-tag">Executive Output</div>
            <h3>No prediction yet</h3>
            <p className="empty-copy">
              Run any input set on the left to update its matching marketplace output.
            </p>
          </div>
        )}
      </div>

      <div className="chart-shell">
        <div className="section-head">
          <div className="chart-title">Dataset Trend</div>
          <div className="chart-meta">
            Source: {datasetMeta.source} | {datasetMeta.count} samples
          </div>
        </div>
        {datasetLoading ? (
          <div className="loading-row">
            <span className="spinner" />
            Loading dataset chart...
          </div>
        ) : (
          <CpuInstanceChart
            points={datasetPoints}
            predictionCpu={inputSets[0]?.cpu === "" ? null : Number(inputSets[0]?.cpu)}
            predictionInstances={primaryResult?.instances}
          />
        )}
      </div>
    </div>
  );
}

export default PredictForm;
