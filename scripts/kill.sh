#!/bin/bash

# ==============================================================================
# AutoArt Kill Script
# Usage: ./scripts/kill.sh
# ==============================================================================

echo "🔪 Killing AutoArt Dev Processes..."

# Helper to kill process by port
kill_port() {
    local port=$1
    local name=$2
    
    echo "   Checking Port $port ($name)..."

    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Windows (Git Bash / Cygwin)
        pid=$(netstat -ano | grep ":$port " | awk '{print $5}' | head -n 1)
        if [ -n "$pid" ]; then
            echo "   Found PID $pid. Killing..."
            taskkill //F //PID "$pid" > /dev/null 2>&1
        fi
    else
        # Linux / MacOS
        pid=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$pid" ]; then
            echo "   Found PID $pid. Killing..."
            kill -9 "$pid" > /dev/null 2>&1
        fi
    fi
}

# Kill Backend (Default Port 8000)
kill_port 8000 "Backend"

# Kill AutoHelper (Default Port 8100)
kill_port 8100 "AutoHelper"

# Kill Frontend (Default Port 5173)
kill_port 5173 "Frontend"

# Kill additional likely Vite ports if user has multiple running
kill_port 5174 "Frontend (Alt)"
kill_port 5175 "Frontend (Alt)"

echo "✅ Done."
