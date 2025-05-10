import datetime
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app_log.txt")

os.makedirs(LOG_DIR, exist_ok=True)

def append_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")
