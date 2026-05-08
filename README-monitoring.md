# MediFlow Observability Stack

This repository contains the Prometheus + Grafana observability stack for MediFlow.

## Prerequisites
- Docker
- Docker Compose v2

## How to start
Run the following command to build and start the services in detached mode:
```bash
make up
```

## Access URLs
- **API**: [http://localhost:8000](http://localhost:8000)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana**: [http://localhost:3000](http://localhost:3000) (Credentials: `admin` / `admin`)

## How to verify Prometheus is scraping
Run `make prom-targets` or navigate to [http://localhost:9090/targets](http://localhost:9090/targets). Ensure the `mediflow-api` job is showing as **UP**.

## How to add a new custom metric
1. **Define in `metrics.py`**: Add your Prometheus metric (Counter, Gauge, Histogram, etc.) and a helper function.
2. **Call helper at usage site**: Import the helper function in `main.py` or your service logic and call it where the event occurs.
3. **Add panel to relevant dashboard JSON**: Add a new panel to the appropriate Grafana dashboard file in `monitoring/grafana/dashboards/` using the metric name.

## How to add a new Grafana panel
You can either:
- **Edit JSON**: Modify the dashboard JSON files in `monitoring/grafana/dashboards/` directly.
- **Use UI then export**: Create the panel in the Grafana UI, go to the dashboard settings, view the JSON model, and copy the panel definition back into the source JSON file.

## How to update alert thresholds
Edit the expressions in `monitoring/alerts.yml` and restart the Prometheus service using `docker compose restart prometheus`.

## Troubleshooting
- **Container name resolution**: Ensure all services are on the same Docker bridge network (`mediflow-net`). Verify with `docker network inspect mediflow-net`.
- **Port conflicts**: If ports 8000, 9090, or 3000 are already in use, stop the conflicting services or change the host port mappings in `docker-compose.yml`.
- **Grafana datasource test failing**: Verify that Grafana is using `http://prometheus:9090` as the URL (not `localhost`) since it needs to route through the Docker network.
