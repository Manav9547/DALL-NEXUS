#!/bin/bash
# NexusID — Start both backend and frontend
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║         NexusID — Starting Up            ║"
echo "╚══════════════════════════════════════════╝"

# Check if DB exists, generate data if not
if [ ! -f "$DIR/nexusid.db" ]; then
    echo "[1/3] Generating synthetic data..."
    python "$DIR/tools/synthetic_data/generate.py"
    echo ""
    echo "[2/3] Running initial pipeline..."
    python -c "
from backend.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
r = client.post('/api/pipeline/run-all')
d = r.json()
print(f'  Pipeline completed in {d[\"elapsed_seconds\"]}s')
print(f'  UBIDs: {d[\"resolution\"][\"active_ubids\"]}')
print(f'  Merges: {d[\"resolution\"][\"merges_performed\"]}')
print(f'  Active: {d[\"activity\"][\"status_distribution\"][\"active\"]}')
print(f'  Dormant: {d[\"activity\"][\"status_distribution\"][\"dormant\"]}')
print(f'  Closed: {d[\"activity\"][\"status_distribution\"][\"closed\"]}')
"
else
    echo "[✓] Database found, skipping data generation"
fi

echo ""
echo "[3/3] Starting servers..."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""

# Start backend
cd "$DIR"
python backend/main.py &
BACKEND_PID=$!

# Start frontend dev server
cd "$DIR/frontend"
npx vite --host 2>/dev/null &
FRONTEND_PID=$!

# Trap ctrl+c
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

echo "Press Ctrl+C to stop both servers"
wait
