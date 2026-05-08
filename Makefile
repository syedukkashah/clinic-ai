.PHONY: up down logs restart metrics-check prom-targets grafana-open ps

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f

restart:
	docker compose restart api

metrics-check:
	curl -s http://localhost:8000/metrics | grep mediflow

prom-targets:
	open http://localhost:9090/targets || xdg-open http://localhost:9090/targets || start http://localhost:9090/targets

grafana-open:
	open http://localhost:3000 || xdg-open http://localhost:3000 || start http://localhost:3000

ps:
	docker compose ps
