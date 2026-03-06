# Development Setup

## Hot-Reload Development

### Option 1: Local Development (Recommended for Frontend)

**Frontend (with hot-reload):**
```bash
cd armor_select/frontend
npm install
npm run dev
```
Frontend will be available at `http://localhost:5173` (Vite default) with hot-reload enabled.

**API (with hot-reload):**
```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn armor_select.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Task Worker:**
```bash
python -m armor_select.task.worker
```

**Redis:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Option 2: Docker with Hot-Reload

Use the development override file:

```bash
# Start all services with hot-reload for API
docker compose -f armor_select/docker/docker-compose.yml -f armor_select/docker/docker-compose.dev.yml up

# Frontend: Still run locally for best hot-reload experience
cd armor_select/frontend
npm run dev
```

**Note:**
- API will hot-reload on code changes (thanks to `--reload` flag and volume mounts)
- Task worker will need container restart for code changes (Python workers don't auto-reload)
- Frontend in Docker is production build - use local `npm run dev` for hot-reload

### Option 3: Hybrid Approach (Best of Both Worlds)

- **Frontend**: Run locally with `npm run dev` (best hot-reload)
- **API, Task, Redis**: Run in Docker with dev overrides

```bash
# Terminal 1: Start backend services
docker compose -f armor_select/docker/docker-compose.yml -f armor_select/docker/docker-compose.dev.yml up api task redis

# Terminal 2: Start frontend locally
cd armor_select/frontend
npm run dev
```

## Production Build

For production, use the standard docker-compose:

```bash
python armor_select/start.py start
```

This builds production images without hot-reload.
