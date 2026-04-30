#!/bin/bash
#
# Waybern Mews OS — Launcher
#
# Usage: double-click this file, or run `bash launch.sh` in Terminal.
#
# To make this double-clickable on macOS:
#   1. Rename this file to launch.command
#   2. Run: chmod +x launch.command
#   3. Double-click it in Finder
#   Alternatively, use Automator: create a new Application, add a
#   "Run Shell Script" action, and paste the contents of this file.
#

# Move to the project root (works regardless of where it's called from)
cd "/Users/barrymorisse/Documents/Waybern Mews BC/Operating System"

# Activate the Python virtual environment
source venv/bin/activate

# Start the FastAPI server in the background (--reload picks up file changes automatically)
uvicorn main:app --reload &

# Wait briefly for the server to start before opening the browser
sleep 1

# Open the app in the default browser
open http://localhost:8000
