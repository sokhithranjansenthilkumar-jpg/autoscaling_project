import React from "react";

function CpuInstanceChart({ points, predictionCpu, predictionInstances }) {
  if (!points || points.length === 0) {
    return (
      <div className="chart-empty">
        No dataset points available to draw chart.
      </div>
    );
  }

  const width = 720;
  const height = 320;
  const pad = 42;

  const cpus = points.map((point) => Number(point.cpu));
  const instances = points.map((point) => Number(point.instances));

  const minCpu = Math.min(...cpus);
  const maxCpu = Math.max(...cpus);
  const minInstances = Math.min(...instances);
  const maxInstances = Math.max(...instances);

  const rangeCpu = Math.max(1, maxCpu - minCpu);
  const rangeInstances = Math.max(1, maxInstances - minInstances);

  const xFor = (cpuValue) =>
    pad + ((Number(cpuValue) - minCpu) / rangeCpu) * (width - pad * 2);
  const yFor = (instanceValue) =>
    height -
    pad -
    ((Number(instanceValue) - minInstances) / rangeInstances) * (height - pad * 2);

  const sortedPoints = [...points].sort((a, b) => Number(a.cpu) - Number(b.cpu));
  const path = sortedPoints
    .map((point, index) => {
      const x = xFor(point.cpu);
      const y = yFor(point.instances);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const hasPrediction =
    Number.isFinite(Number(predictionCpu)) &&
    Number.isFinite(Number(predictionInstances));

  const gridLines = 4;
  const yTicks = Array.from({ length: gridLines + 1 }, (_, index) => {
    const value = minInstances + (rangeInstances / gridLines) * index;
    return {
      label: value.toFixed(value % 1 === 0 ? 0 : 1),
      y: yFor(value),
    };
  });

  return (
    <div>
      <div className="chart-legend">
        <span className="legend-item">
          <span className="legend-swatch trend" />
          Historical dataset
        </span>
        <span className="legend-item">
          <span className="legend-swatch prediction" />
          Current prediction
        </span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="chart-svg"
      >
        {yTicks.map((tick) => (
          <g key={tick.label}>
            <line
              x1={pad}
              y1={tick.y}
              x2={width - pad}
              y2={tick.y}
              className="grid-line"
            />
            <text x={8} y={tick.y + 4} className="axis-text">
              {tick.label}
            </text>
          </g>
        ))}
        <line
          x1={pad}
          y1={height - pad}
          x2={width - pad}
          y2={height - pad}
          className="axis-line"
        />
        <line
          x1={pad}
          y1={pad}
          x2={pad}
          y2={height - pad}
          className="axis-line"
        />
        <path d={path} className="trend-line" />
        {points.map((point, index) => (
          <circle
            key={`${point.cpu}-${point.instances}-${index}`}
            cx={xFor(point.cpu)}
            cy={yFor(point.instances)}
            r="3.5"
            className="dot"
          />
        ))}
        {hasPrediction && (
          <>
            <line
              x1={xFor(predictionCpu)}
              y1={height - pad}
              x2={xFor(predictionCpu)}
              y2={yFor(predictionInstances)}
              className="prediction-guide"
            />
            <circle
              cx={xFor(predictionCpu)}
              cy={yFor(predictionInstances)}
              r="6"
              className="prediction-dot"
            />
          </>
        )}
        <text x={width / 2} y={height - 8} className="axis-text center">
          CPU usage (%)
        </text>
        <text x={8} y={18} className="axis-text">
          Instances
        </text>
      </svg>
      <div className="chart-labels">
        <span>CPU {minCpu}%</span>
        <span>CPU {maxCpu}%</span>
      </div>
    </div>
  );
}

export default CpuInstanceChart;
