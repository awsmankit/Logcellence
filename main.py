from fastapi import FastAPI
import asyncio
import nats
import yaml
import httpx
from datetime import datetime
from typing import List, Dict, DefaultDict
from collections import defaultdict
import logging
import re
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("log-summarizer")

app = FastAPI()

# Load OpenAI config from a yaml file
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

OPENAI_API_KEY = config["openai"]["api_key"]
OPENAI_API_VERSION = config["openai"]["api_version"]
OPENAI_ENDPOINT = config["openai"]["azure_endpoint_chat"]
OPENAI_DEPLOYMENT_ID = config["openai"]["deployment_id"]

NATS_URL = "nats://localhost:4222"
SUBJECT = "logs.stream"

log_buffers: DefaultDict[str, List[str]] = defaultdict(list)
summarized_logs: DefaultDict[str, List[Dict]] = defaultdict(list)

BUFFER_SIZE = 10
SUMMARY_INTERVAL = 300  # 5 minutes
last_summary_times: DefaultDict[str, datetime] = defaultdict(lambda: datetime.now())
nc = None  # NATS client

SERVICE_PATTERN = r'\[([A-Za-z0-9_-]+)\]'
DEFAULT_SERVICE = "unknown"

def extract_service_name(log_message: str) -> str:
    match = re.search(SERVICE_PATTERN, log_message)
    if match:
        return match.group(1)
    return DEFAULT_SERVICE

# ✨ Short Summary Version ✨
async def summarize_logs(service: str, logs: List[str]):
    if not logs:
        return "No logs to summarize."

    logs_text = "\n".join(logs)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": """
You are a helpful assistant that reads batches of application logs and generates a categorized, human-readable summary.

Rules:
- Categorize the logs into three groups:
  - ✅ Successful operations
  - ⚠️ Warnings
  - ❌ Errors
- Under each group, briefly describe key patterns or major events.
- Group similar log types together and mention counts if possible (e.g., 35 successful DAG runs).
- Summarize patterns and repeated issues concisely, not every log line individually.
- Maintain a clear and professional tone.
- The output must be plain text and easy for humans to read. No JSON, no bullet points unless grouping by category as shown below.

Input:
{logs}

Output Format Example:
✅ Successful operations
- 35 successful DAG runs (Airflow)
- 120 successful API requests (API Gateway)

⚠️ Warnings
- Redis cache miss spike observed between 12:00–12:30 PM.
- Minor delay in DAG scheduling (Airflow scheduler lag: 10 seconds).

❌ Errors
- 2 DAG failures (Airflow): "PreprocessingPipeline_DAG" timeout after 30 min.
- API timeout: 5xx server error at /process-claim (12:15 PM).
"""
            },
            {
                "role": "user",
                "content": f"Summarize these logs for service '{service}' in the above style:\n\n{logs_text}"
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{OPENAI_ENDPOINT}/openai/deployments/{OPENAI_DEPLOYMENT_ID}/chat/completions?api-version={OPENAI_API_VERSION}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            short_summary = data['choices'][0]['message']['content']
            return short_summary
    except Exception as e:
        logger.error(f"Error summarizing logs for service '{service}': {e}")
        return f"Error summarizing logs: {e}"

async def process_log_buffer(service: str):
    logger.info(f"Processing log buffer for service '{service}' with {len(log_buffers[service])} logs")
    
    if log_buffers[service]:
        summary = await summarize_logs(service, log_buffers[service].copy())

        summarized_logs[service].append({
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "log_count": len(log_buffers[service])
        })

        if len(summarized_logs[service]) > 10:
            summarized_logs[service].pop(0)

        log_buffers[service].clear()
        last_summary_times[service] = datetime.now()

        logger.info(f"✅ Short Summary generated for service '{service}'")
        logger.info(f"📋 Short Summary Content:\n{summary}")
        await push_summary_to_loki(service, summary)
        return summary
    return None

async def process_all_services():
    results = {}
    for service, logs in log_buffers.items():
        if logs:
            summary = await process_log_buffer(service)
            if summary:
                results[service] = "Summarized"
    return results

async def nats_consumer():
    global nc

    async def message_handler(msg):
        subject = msg.subject
        data = msg.data.decode()

        # Try to parse as JSON
        try:
            event = json.loads(data)
            service = event.get("service", DEFAULT_SERVICE)
            message = event.get("message", data)
        except Exception as e:
            logger.warning(f"Failed to parse log as JSON, falling back to regex: {e}")
            service = extract_service_name(data)
            message = data

        log_buffers[service].append(message)
        logger.info(f"Received log for service '{service}'. Buffer size: {len(log_buffers[service])}/{BUFFER_SIZE}")

        if len(log_buffers[service]) >= BUFFER_SIZE:
            logger.info(f"Buffer size for service '{service}' reached threshold, processing...")
            await process_log_buffer(service)

    while True:
        try:
            logger.info(f"Connecting to NATS at {NATS_URL}...")
            nc = await nats.connect(servers=[NATS_URL], reconnect_time_wait=2)
            logger.info(f"Connected to NATS")

            await nc.subscribe(SUBJECT, cb=message_handler)
            logger.info(f"Subscribed to NATS subject '{SUBJECT}'")

            asyncio.create_task(timed_force_summarizer())

            while nc.is_connected:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"NATS connection error: {e}")
            if nc:
                try:
                    await nc.close()
                except:
                    pass
            await asyncio.sleep(5)
            logger.info("Attempting to reconnect to NATS...")

async def timed_force_summarizer():
    logger.info("Started timed summarizer background task")
    while True:
        now = datetime.now()
        for service, last_time in last_summary_times.items():
            time_since_last_summary = (now - last_time).total_seconds()
            if service in log_buffers and log_buffers[service] and time_since_last_summary >= SUMMARY_INTERVAL:
                logger.info(f"Timed summarizer: Forcing summary for service '{service}' after {time_since_last_summary:.0f} seconds")
                await process_log_buffer(service)
        await asyncio.sleep(30)
        
async def push_summary_to_loki(service: str, summary: str):
    loki_url = "http://localhost:3100/loki/api/v1/push"  # or your Loki URL
    timestamp_ns = str(int(datetime.utcnow().timestamp() * 1e9))  # nanoseconds format required by Loki

    payload = {
        "streams": [
            {
                "stream": {
                    "service": service,
                    "type": "summary"
                },
                "values": [
                    [timestamp_ns, summary]
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(loki_url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"📥 Short summary for service '{service}' pushed to Loki")
    except Exception as e:
        logger.error(f"Failed to push summary to Loki for service '{service}': {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(nats_consumer())
    logger.info("Application started, NATS consumer task initialized")

# === API Routes ===

@app.get("/")
async def root():
    global nc
    services_status = {
        service: {
            "logs_in_buffer": len(logs),
            "summaries_available": len(summarized_logs[service]),
            "time_since_last_summary": (datetime.now() - last_summary_times[service]).total_seconds()
        } for service, logs in log_buffers.items()
    }
    return {
        "status": "ok",
        "nats_connected": nc is not None and nc.is_connected,
        "services": services_status,
        "total_services_tracked": len(log_buffers)
    }

@app.get("/summarized_logs")
async def get_all_summarized_logs():
    return {"services": summarized_logs}

@app.get("/summarized_logs/{service}")
async def get_service_summarized_logs(service: str):
    if service in summarized_logs:
        return {"service": service, "summaries": summarized_logs[service]}
    return {"service": service, "summaries": [], "message": "No summaries available for this service"}

@app.post("/force_summarize")
async def force_summarize_all():
    logger.info("Manual summarization requested for all services")
    results = await process_all_services()
    return {
        "status": "summarization_complete",
        "results": results
    }

@app.post("/force_summarize/{service}")
async def force_summarize_service(service: str):
    if service in log_buffers and log_buffers[service]:
        logger.info(f"Manual summarization requested for service '{service}'")
        summary = await process_log_buffer(service)
        return {"status": "summarized", "service": service, "summary": summary}
    return {"status": "no_logs_to_summarize", "service": service}

@app.get("/raw_logs/{service}")
async def get_service_raw_logs(service: str):
    if service in log_buffers:
        return {"service": service, "logs": log_buffers[service], "count": len(log_buffers[service])}
    return {"service": service, "logs": [], "count": 0}

@app.get("/services")
async def get_services():
    all_services = list(set(list(log_buffers.keys()) + list(summarized_logs.keys())))
    return {"services": all_services}

@app.post("/add_test_logs")
async def add_test_logs(service: str, count: int = 1):
    for i in range(count):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_log = f"[{service}] ERROR [{timestamp}] Test error log {i+1}: Database connection failed - timeout after 30s"
        
        extracted_service = extract_service_name(test_log)
        log_buffers[extracted_service].append(test_log)
    
    logger.info(f"Added {count} test logs for service '{service}'. Buffer size: {len(log_buffers[service])}/{BUFFER_SIZE}")
    
    if len(log_buffers[service]) >= BUFFER_SIZE:
        asyncio.create_task(process_log_buffer(service))
        return {"status": "logs_added", "service": service, "buffer_size": len(log_buffers[service]), "processing": "started"}
    
    return {"status": "logs_added", "service": service, "buffer_size": len(log_buffers[service])}
