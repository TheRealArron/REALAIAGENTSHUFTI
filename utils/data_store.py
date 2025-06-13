"""
Data storage utilities for the Shufti agent
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading
from utils.logger import log_info, log_error, log_warning


class DataStore:
    """Thread-safe data storage for job listings and agent state"""

    def __init__(self, data_file: str = "shufti_data.json"):
        self.data_file = Path(data_file)  # Convert to Path object
        self.lock = threading.Lock()
        self.data = {
            "jobs": {},
            "applications": {},
            "agent_state": {},
            "messages": [],
            "config": {}
        }
        self.load_data()

    def load_data(self):
        """Load data from JSON file"""
        try:
            if self.data_file.exists():  # Now this will work
                with self.data_file.open('r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Update with loaded data while preserving structure
                    for key in self.data:
                        if key in loaded_data:
                            self.data[key] = loaded_data[key]
                log_info(f"Loaded data from {self.data_file}")
            else:
                log_info(f"Data file {self.data_file} not found, starting with empty data")
        except Exception as e:
            log_error(f"Failed to load data from {self.data_file}: {str(e)}")

    def save_data(self):
        """Save data to JSON file"""
        try:
            with self.lock:
                # Create directory if it doesn't exist
                self.data_file.parent.mkdir(parents=True, exist_ok=True)

                # Use absolute path and ensure proper file handling
                with self.data_file.open('w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
                log_info(f"Saved data to {self.data_file}")
        except Exception as e:
            log_error(f"Failed to save data to {self.data_file}: {str(e)}")

    def store_job(self, job_id: str, job_data: Dict[str, Any]):
        """Store job listing data"""
        with self.lock:
            self.data["jobs"][job_id] = {
                **job_data,
                "stored_at": datetime.now().isoformat()
            }
        self.save_data()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job data by ID"""
        with self.lock:
            return self.data["jobs"].get(job_id)

    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all stored jobs"""
        with self.lock:
            return self.data["jobs"].copy()

    def store_application(self, job_id: str, application_data: Dict[str, Any]):
        """Store application data"""
        with self.lock:
            self.data["applications"][job_id] = {
                **application_data,
                "applied_at": datetime.now().isoformat()
            }
        self.save_data()

    def get_application(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get application data by job ID"""
        with self.lock:
            return self.data["applications"].get(job_id)

    def get_all_applications(self) -> Dict[str, Dict[str, Any]]:
        """Get all applications"""
        with self.lock:
            return self.data["applications"].copy()

    def update_agent_state(self, state_data: Dict[str, Any]):
        """Update agent state"""
        with self.lock:
            self.data["agent_state"].update(state_data)
            self.data["agent_state"]["updated_at"] = datetime.now().isoformat()
        self.save_data()

    def get_agent_state(self) -> Dict[str, Any]:
        """Get current agent state"""
        with self.lock:
            return self.data["agent_state"].copy()

    def add_message(self, message_data: Dict[str, Any]):
        """Add a message to the log"""
        with self.lock:
            message_data["timestamp"] = datetime.now().isoformat()
            self.data["messages"].append(message_data)

            # Keep only last 1000 messages to prevent file from growing too large
            if len(self.data["messages"]) > 1000:
                self.data["messages"] = self.data["messages"][-1000:]
        self.save_data()

    def get_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent messages"""
        with self.lock:
            return self.data["messages"][-limit:] if self.data["messages"] else []

    def set_config(self, key: str, value: Any):
        """Set configuration value"""
        with self.lock:
            self.data["config"][key] = value
        self.save_data()

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        with self.lock:
            return self.data["config"].get(key, default)

    def clear_old_jobs(self, days_old: int = 30):
        """Clear jobs older than specified days"""
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)

        with self.lock:
            jobs_to_remove = []
            for job_id, job_data in self.data["jobs"].items():
                try:
                    stored_at = datetime.fromisoformat(job_data.get("stored_at", ""))
                    if stored_at.timestamp() < cutoff_date:
                        jobs_to_remove.append(job_id)
                except (ValueError, TypeError):
                    # If date parsing fails, consider it old
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.data["jobs"][job_id]

            if jobs_to_remove:
                log_info(f"Removed {len(jobs_to_remove)} old jobs")

        if jobs_to_remove:
            self.save_data()

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self.lock:
            return {
                "total_jobs": len(self.data["jobs"]),
                "total_applications": len(self.data["applications"]),
                "total_messages": len(self.data["messages"]),
                "data_file_size": self.data_file.stat().st_size if self.data_file.exists() else 0,
                "last_updated": self.data["agent_state"].get("updated_at", "Never")
            }

    def backup_data(self, backup_file: Optional[str] = None):
        """Create a backup of current data"""
        if backup_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"shufti_backup_{timestamp}.json"

        backup_path = Path(backup_file)
        try:
            with self.lock:
                with backup_path.open('w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
            log_info(f"Data backed up to {backup_path}")
            return str(backup_path)
        except Exception as e:
            log_error(f"Failed to backup data: {str(e)}")
            return None

    def restore_from_backup(self, backup_file: str):
        """Restore data from backup file"""
        backup_path = Path(backup_file)
        try:
            if backup_path.exists():
                with backup_path.open('r', encoding='utf-8') as f:
                    backup_data = json.load(f)

                with self.lock:
                    self.data = backup_data

                self.save_data()
                log_info(f"Data restored from {backup_path}")
                return True
            else:
                log_error(f"Backup file {backup_path} not found")
                return False
        except Exception as e:
            log_error(f"Failed to restore from backup: {str(e)}")
            return False

    def __del__(self):
        """Ensure data is saved when object is destroyed"""
        try:
            self.save_data()
        except:
            pass  # Ignore errors during cleanup


# Global data store instance
data_store = DataStore()


def get_data_store() -> DataStore:
    """Get the global data store instance"""
    return data_store


# Convenience functions for common operations
def store_job_data(job_id: str, job_data: Dict[str, Any]):
    """Store job data using global data store"""
    data_store.store_job(job_id, job_data)


def get_job_data(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job data using global data store"""
    return data_store.get_job(job_id)


def store_application_data(job_id: str, application_data: Dict[str, Any]):
    """Store application data using global data store"""
    data_store.store_application(job_id, application_data)


def get_application_data(job_id: str) -> Optional[Dict[str, Any]]:
    """Get application data using global data store"""
    return data_store.get_application(job_id)


def log_agent_message(message_type: str, content: str, metadata: Optional[Dict[str, Any]] = None):
    """Log agent message using global data store"""
    message_data = {
        "type": message_type,
        "content": content,
        "metadata": metadata or {}
    }
    data_store.add_message(message_data)