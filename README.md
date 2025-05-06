# 📘 Centralized Logging System (On-Prem) with GPT Summarization & Grafana Dashboards

> Real-time, AI-enhanced observability stack using **Fluent Bit**, **Loki**, **Grafana**, **Vector**, **NATS**, **FastAPI**, and **Azure OpenAI**.

---

## 📦 Folder Structure

```
CENTRALISED_LOGGING/
├── tools/
│   ├── loki-linux-amd64.zip
│   ├── nats-0.2.2-amd64.deb
│   ├── nats-server-v2.11.2-amd64.deb
│   ├── vector-x86_64-unknown-linux-gnu.tar.gz
├── vector-x86_64-unknown-linux-gnu/
├── config.yaml
├── loki
├── loki-config.yaml
├── main.py
├── makefile
├── push_random_logs.py
├── test_azure_openai.py
├── vector.yaml
└── README.md  ← You are here
```

📁 Tool Downloads — Installation Folder
📌 Always store and extract/install all third-party tool binaries (.deb, .zip, .tar.gz) inside the tools/ directory.
This keeps the root project clean and makes tracking/upgrading tools easier.

For example:

bash
Copy
Edit
cd tools/
wget https://github.com/grafana/loki/releases/latest/download/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
mv loki-linux-amd64 ../loki

---

## 🧰 Tech Stack Summary

| Component         | Role                                                            |
| ----------------- | --------------------------------------------------------------- |
| **Vector**        | Collects/transforms `.log` files and forwards to Loki & NATS    |
| **Loki**          | Log database queried by Grafana and FastAPI                     |
| **Grafana**       | Dashboards and real-time log visualizations                     |
| **Fluent Bit**    | Lightweight log shipping agent for tailing system/service logs  |
| **NATS**          | Lightweight messaging bus between Vector → FastAPI              |
| **FastAPI**       | Consumes logs via NATS, summarizes with GPT, and pushes to Loki |
| **Azure OpenAI**  | GPT model generates natural language log summaries              |
| **Python Script** | Synthetic logs generator (DDMS, DPMS, OCR, etc.)                |

---

## 🔁 Architecture Flow

```plaintext
+-------------+    +-----------+     +-----------+     +----------+     +-------------+
| Services    | -> |   Logs    | --> |  Vector   | --> |   Loki   | --> |   Grafana   |
| (Airflow,   |    | (*.log)   |     |           |     |          |     | Dashboards  |
| DDMS, etc.) |    +-----------+     +-----------+     +----------+     +-------------+
                                    |                        |
                                    v                        v
                                +--------+         +----------------+
                                |  NATS  |-------> |   FastAPI App  |
                                +--------+         | (GPT Summary)  |
                                                   +----------------+
                                                           |
                                                   +-------------------+
                                                   | Azure OpenAI GPT |
                                                   +-------------------+
```

---

## ⚙️ Setup Instructions

### 🔹 1. Install Loki

```bash
wget https://github.com/grafana/loki/releases/latest/download/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
mv loki-linux-amd64 loki
chmod +x loki
```

Create `loki-config.yaml`:

```yaml
auth_enabled: false
server:
  http_listen_port: 3100
ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 3m
  chunk_retain_period: 1m
schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
storage_config:
  boltdb_shipper:
    active_index_directory: /tmp/loki/index
    cache_location: /tmp/loki/cache
  filesystem:
    directory: /tmp/loki/chunks
limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
```

Run Loki:

```bash
./loki -config.file=loki-config.yaml
curl http://localhost:3100/ready
```

---

### 🔹 2. Install Fluent Bit

```bash
sudo apt install fluent-bit
sudo fluent-bit -c fluent-bit.conf
```

Make sure your `fluent-bit.conf` outputs to Loki at `http://localhost:3100`.

---

### 🔹 3. Install Grafana

```bash
sudo apt install -y apt-transport-https software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/grafana.gpg
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

Visit: [http://localhost:3000](http://localhost:3000)

---

### 🔹 4. Install NATS

```bash
sudo dpkg -i tools/nats-server-v2.11.2-amd64.deb
sudo apt-get install -f  # if needed
nats-server -js &
```

---

### 🔹 5. Install Vector

```bash
tar -xvzf tools/vector-x86_64-unknown-linux-gnu.tar.gz
cd vector-x86_64-unknown-linux-gnu
sudo mv vector /usr/local/bin/
vector --version
```

Run using:

```bash
vector -c vector.yaml
```

---

## 📊 Grafana Dashboard Examples

| Panel       | LogQL Example                                       | Description              |                                |
| ----------- | --------------------------------------------------- | ------------------------ | ------------------------------ |
| Log Stream  | `{job="airflow"}`                                   | All logs from Airflow    |                                |
| Heatmap     | `{level="ERROR"}`                                   | Error spikes over time   |                                |
| GPT Summary | `{type="summary"}`                                  | Summarized logs from GPT |                                |
| Pie Chart   | `count_over_time({service=~".*"}[5m]) by (service)` | Log volume by service    |                                |
| Table Panel | \`{type="summary"}                                  | json\`                   | Structured summary with fields |

---

## 🚀 Features

* 🔁 **Real-time log shipping & indexing**
* 🤖 **Log summarization using GPT**
* 📈 **Dashboards, filters, and alerts**
* ⚡ **Synthetic log generation (testing)**
* 🔐 **Optional RBAC + Grafana Auth**
* 📁 **Multi-service support (Airflow, DDMS, OCR, etc.)**

---

## 💡 Ideas for Future Enhancements

| Feature                       | Benefit                       |
| ----------------------------- | ----------------------------- |
| Alerting in Grafana           | Proactive monitoring          |
| Annotations from GPT          | Overlay summaries on heatmaps |
| JSON logging with fields      | Richer querying and grouping  |
| Slack or Webhook integrations | Team-level alert delivery     |
| Extend to 8 services          | Unified observability stack   |

---

## 🧪 Test It

Use:

```bash
python push_random_logs.py
```

To generate test logs (mimics DDMS, DPMS, etc.) and validate the flow across all services.

---
