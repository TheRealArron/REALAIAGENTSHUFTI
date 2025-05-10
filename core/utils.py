# core/utils.py

import os
import logging

def setup_logging(log_file="session_log.txt"):
    """
    Sets up the logging configuration for the application.
    Logs messages to both console and a log file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, mode="a", encoding="utf-8")
        ]
    )
    logging.info("Logging setup complete.")


def append_log(message, log_file="session_log.txt"):
    """
    Appends a message to the log file and console.
    """
    logging.info(message)  # Logs to console
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{message}\n")  # Appends message to log file


def read_file(file_path):
    """
    Reads the content of a file and returns it as a string.
    """
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    else:
        logging.error(f"File not found: {file_path}")
        return None


def write_file(file_path, content):
    """
    Writes content to a file.
    """
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)
    logging.info(f"Content written to {file_path}")


def get_dict_from_file(file_path):
    """
    Reads a file and attempts to convert it into a dictionary (JSON or similar format).
    """
    try:
        content = read_file(file_path)
        if content:
            return eval(content)  # Converts string to a dictionary, for example from a JSON-like structure.
        return None
    except Exception as e:
        logging.error(f"Error parsing file {file_path}: {e}")
        return None
