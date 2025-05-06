# Makefile

# Default NATS data directory
NATS_DATA_DIR=$(HOME)/nats-data/jetstream

.PHONY: nats grafana loki vector all

# Start NATS Server with JetStream enabled
nats:
	nats-server -js --store_dir $(NATS_DATA_DIR)

# Start Grafana server using systemctl
grafana:
	sudo systemctl start grafana-server

# Start Loki with specified config
loki:
	./loki -config.file=loki-config.yaml

# Start Vector with specified config
vector:
	sudo vector -c vector.yaml

summary:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

log_pusher:
	python3 push_random_logs.py

# Start all services
all: nats grafana loki vector



