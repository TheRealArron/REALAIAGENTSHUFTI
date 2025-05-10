import tkinter as tk
from tkinter import messagebox, scrolledtext
import asyncio
import threading
from pipeline import run_agent_with_name  # Import the agent runner function

# Function to start the agent asynchronously in a separate thread
def start_agent():
    email = email_entry.get().strip()
    password = password_entry.get().strip()
    name = name_entry.get().strip()
    skills = [skill.strip() for skill in skills_entry.get().split(',') if skill.strip()]
    bio = bio_entry.get().strip()

    # Validate inputs
    if not email or not password or not name or not bio:
        messagebox.showerror("Missing Info", "Please enter email, password, name, and bio.")
        return

    # Disable the start button to prevent multiple clicks while agent is running
    start_button.config(state=tk.DISABLED)
    append_log("[INFO] Starting job agent...\n")

    # Function to run the agent asynchronously
    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_agent_with_name(
                email, password, name, skills, bio, log_callback=append_log
            ))
        except Exception as e:
            append_log(f"[ERROR] {e}\n")
        finally:
            append_log("[INFO] Agent process finished.\n")
            start_button.config(state=tk.NORMAL)
            loop.close()

    # Start the agent process in a separate thread
    threading.Thread(target=run_async_task, daemon=True).start()

# Function to append logs to the status box and save to a file
def append_log(message):
    status_box.insert(tk.END, message)
    status_box.see(tk.END)
    with open("session_log.txt", "a", encoding="utf-8") as f:
        f.write(message)

# GUI Layout
root = tk.Tk()
root.title("AI Job Agent")

# Create labels and entry widgets for email, password, etc.
labels = ["Email:", "Password:", "Agent Name:", "Skills (comma separated):", "Bio:"]
for i, label in enumerate(labels):
    tk.Label(root, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")

email_entry = tk.Entry(root, width=40)
password_entry = tk.Entry(root, width=40, show="*")
name_entry = tk.Entry(root, width=40)
skills_entry = tk.Entry(root, width=40)
bio_entry = tk.Entry(root, width=40)

entries = [email_entry, password_entry, name_entry, skills_entry, bio_entry]
for i, entry in enumerate(entries):
    entry.grid(row=i, column=1, padx=10, pady=5)

# Start button
start_button = tk.Button(root, text="Start Agent", command=start_agent)
start_button.grid(row=5, column=0, columnspan=2, pady=10)

# Status and log output
tk.Label(root, text="Status:").grid(row=6, column=0, columnspan=2)
status_box = scrolledtext.ScrolledText(root, width=70, height=20, state=tk.NORMAL)
status_box.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

# Start the GUI loop
root.mainloop()
