export function parsePrometheusText(rawText = "") {
  const metrics = new Map();
  const help = new Map();
  const types = new Map();

  String(rawText)
    .split(/\r?\n/)
    .forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      if (trimmed.startsWith("# HELP ")) {
        const [, name, ...description] = trimmed.split(/\s+/);
        help.set(name, description.join(" "));
        return;
      }

      if (trimmed.startsWith("# TYPE ")) {
        const [, name, type] = trimmed.split(/\s+/);
        types.set(name, type);
        return;
      }

      if (trimmed.startsWith("#")) return;

      const sample = parseSampleLine(trimmed);
      if (!sample) return;
      const baseName = sample.name.replace(/_(bucket|sum|count|created)$/, "");
      const metricName = types.has(sample.name) ? sample.name : baseName;
      const existing = metrics.get(metricName) || {
        name: metricName,
        type: types.get(metricName) || inferType(sample.name),
        help: help.get(metricName) || "",
        samples: [],
        value: 0,
        labels: {},
      };

      existing.samples.push(sample);
      existing.value = sample.value;
      existing.labels = sample.labels;
      existing.type = types.get(metricName) || existing.type;
      existing.help = help.get(metricName) || existing.help;
      metrics.set(metricName, existing);
    });

  return metrics;
}

function parseSampleLine(line) {
  const match = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+]?[\d.]+(?:e[-+]?\d+)?|NaN|Inf|-Inf)(?:\s+\d+)?$/i);
  if (!match) return null;
  return {
    name: match[1],
    labels: parseLabels(match[2]),
    value: Number(match[3]),
  };
}

function parseLabels(labelText = "") {
  const labels = {};
  if (!labelText) return labels;
  const regex = /(\w+)="((?:\\"|[^"])*)"/g;
  let match;
  while ((match = regex.exec(labelText))) {
    labels[match[1]] = match[2].replace(/\\"/g, '"');
  }
  return labels;
}

function inferType(name) {
  if (/_bucket$|_sum$|_count$/.test(name)) return "histogram";
  if (/_total$/.test(name)) return "counter";
  return "gauge";
}

export function getMetricValue(metrics, name, fallback = 0) {
  return Number(metrics?.get(name)?.value ?? fallback);
}

export function getMetricSamples(metrics, name) {
  return metrics?.get(name)?.samples || [];
}
