import random
import time
import os
import json
from datetime import datetime

# Simulated directories for different services
log_dirs = {
    "ddms": "/home/ankit/centralised_logging/services/DDMS/logs/",
    "dpms": "/home/ankit/centralised_logging/services/DPMS/logs/",
    "ocr": "/home/ankit/centralised_logging/services/OCR/logs/",
}

# Predefined realistic statuses
statuses = ["received", "processing", "validated", "failed", "completed"]

# Predefined operations
operations = ["OCR", "Validation", "Extraction", "Persistence"]

# Log levels with realistic examples
log_levels = {
    "INFO": [
        "Claim received and queued",
        "Page processed successfully",
        "OCR completed",
        "Validation passed",
        "Claim marked as completed"
    ],
    "WARNING": [
        "Slow response during OCR phase",
        "Validation took longer than expected",
        "Missing optional metadata fields",
        "Partial data detected in claim payload",
        "Retrying extraction step"
    ],
    "ERROR": [
        "SQLAlchemy OperationalError: could not connect to server",
        "Pydantic ValidationError: required field missing",
        "PermissionError: Cannot write to /restricted/data",
        "TimeoutError: Request to external API timed out",
        "AssertionError: Page ID not found in claim"
    ],
    "CRITICAL": [
        "System crash during persistence layer",
        "Fatal error in OCR engine",
        "Security breach attempt detected",
        "Unhandled exception: NullReference in validation service",
        "Core dump generated in extraction module"
    ]
}

# Fake stack trace examples
stack_traces = [
    "Traceback (most recent call last):\n  File \"ocr_service.py\", line 128, in process_page\n    ocr_text = ocr_engine.extract(page_image)\nAttributeError: 'NoneType' object has no attribute 'extract'",
    "Traceback (most recent call last):\n  File \"validation.py\", line 55, in validate_claim\n    assert claim['claim_id'] is not None\nAssertionError"
]

# Function to generate realistic claim logs
def generate_realistic_log(service_name):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    level = random.choices(list(log_levels.keys()), weights=[60, 25, 10, 5], k=1)[0]
    message = random.choice(log_levels[level])
    module = random.choice(operations)
    function = "handler"
    line_number = random.randint(10, 300)
    claim_id = f"CLM-{random.randint(10000,99999)}"
    page_id = random.randint(1, 10)
    status = random.choice(statuses)
    latency_ms = random.randint(100, 3000)
    user_id = random.randint(1000, 9999)

    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "service": service_name,
        "module": module,
        "function": function,
        "line": line_number,
        "claim_id": claim_id,
        "page_id": page_id,
        "status": status,
        "latency_ms": latency_ms,
        "user_id": user_id,
        "message": message
    }

    # Occasionally add stack trace for critical logs
    if level == "CRITICAL" and random.random() < 0.7:
        log_entry["stack_trace"] = random.choice(stack_traces)

    return json.dumps(log_entry)

# Helper to get latest log file
def get_latest_log_file(log_dir):
    try:
        files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        print(f"Error accessing log directory {log_dir}: {e}")
        return None

# Main pushing function
def push_logs():
    while True:
        service = random.choice(list(log_dirs.keys()))
        log_dir = log_dirs[service]
        log_path = get_latest_log_file(log_dir)

        if log_path is None:
            print(f"No log files found for {service}.")
            time.sleep(5)
            continue

        log_json = generate_realistic_log(service)

        try:
            with open(log_path, "a") as f:
                f.write(log_json + "\n")
            print(f"Wrote JSON log to {service}: {log_json}")
        except Exception as e:
            print(f"Failed to write log: {e}")

        time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    push_logs()
