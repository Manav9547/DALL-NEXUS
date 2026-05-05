.PHONY: setup seed pipeline run clean test

setup:
	pip install -r backend/requirements.txt --break-system-packages -q
	cd frontend && npm install

seed:
	rm -f nexusid.db
	python tools/synthetic_data/generate.py

pipeline:
	python -c "\
from backend.main import app; \
from fastapi.testclient import TestClient; \
c = TestClient(app); \
r = c.post('/api/pipeline/run-all'); \
d = r.json(); \
print(f'Done in {d[\"elapsed_seconds\"]}s: {d[\"resolution\"][\"active_ubids\"]} UBIDs, {d[\"resolution\"][\"merges_performed\"]} merges')"

run:
	bash run.sh

backend:
	python backend/main.py

frontend:
	cd frontend && npx vite

build:
	cd frontend && npx vite build

clean:
	rm -f nexusid.db
	rm -rf frontend/dist frontend/node_modules

reset: clean seed pipeline

test:
	python -c "\
from backend.main import app; \
from fastapi.testclient import TestClient; \
c = TestClient(app); \
print('Stats:', c.get('/api/stats').json().get('total_ubids'), 'UBIDs'); \
v = c.post('/api/ledger/verify').json(); \
print('Ledger:', 'PASS' if v['verified'] else 'FAIL', f'({v[\"entries\"]} entries)'); \
fq = c.get('/api/query/active-not-inspected?pincode=560058&months_threshold=18').json(); \
print(f'Flagship query: {fq[\"count\"]} results in {fq[\"latency_ms\"]:.0f}ms')"
