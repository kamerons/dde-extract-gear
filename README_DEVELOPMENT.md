# Development Setup

## Configuration

The API and task worker read configuration from **config.yaml** (no .env). Create it from the template:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` as needed (Redis, data paths, extract scale and augmentation, box detector settings). For Docker, `config.yaml` is mounted into the containers; ensure it exists before running `python start.py start`.
Optionally set `CONFIG_PATH` to an absolute path to use a config file elsewhere.

## Hot-Reload Development

### Option 1: Local Development (Recommended for Frontend)

**Frontend (with hot-reload):**
```bash
cd frontend
npm install
npm run dev
```
Frontend will be available at `http://localhost:5173` (Vite default) with hot-reload enabled.

**API (with hot-reload):**
```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload (from repo root)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Task Worker:**
```bash
python -m task.worker
```

**Redis:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Option 2: Docker with Hot-Reload

Use the development override file:

```bash
# Start all services with hot-reload for API (from repo root)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up

# Frontend: Still run locally for best hot-reload experience
cd frontend
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
# Terminal 1: Start backend services (from repo root)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up api task redis

# Terminal 2: Start frontend locally
cd frontend
npm run dev
```

## Start script (python start.py)

From the repo root:

```bash
python start.py start
```

This starts all containers in dev mode (API hot-reload, source mounts). **Images are only built when missing**, so subsequent runs are fast. After changing a Dockerfile or `requirements.txt`, force a rebuild with:

```bash
python start.py start --build
```

## GPU acceleration (training / task worker)

The **task** service runs TensorFlow/Keras for training and inference. To use your NVIDIA GPU inside the task container:

### 1. Host setup

- **NVIDIA driver**: Install the appropriate driver for your GPU (e.g. from [NVIDIA](https://www.nvidia.com/Download/index.aspx) or your distro). Verify with `nvidia-smi`.
- **NVIDIA Container Toolkit**: So Docker can pass the GPU into the container.

  **Ubuntu/Debian:**
  ```bash
  distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
  curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
  curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  ```
  Then restart Docker: `sudo systemctl restart docker` (or restart the Docker daemon your system uses).

  **Other distros:** See [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

### 2. Compose configuration

`docker/docker-compose.yml` already reserves one GPU for the task service (`deploy.resources.reservations.devices`). To use all GPUs, edit the task service and set `count: all` instead of `count: 1`.

To run the **task** container **without GPU** (CPU only) with a **12 GB RAM** limit, use:

```bash
python start.py start --no-gpu
```

To use the GPU again, run `python start.py stop` then `python start.py start` (without `--no-gpu`).

### 3. Verify

After bringing the stack up, check that the task container sees the GPU:

```bash
docker exec armor_select_task nvidia-smi
```

If the toolkit or driver is missing, the task will still run but TensorFlow will log that the GPU is not used and will use CPU instead.

The task image is based on `tensorflow/tensorflow:2.15.0-gpu`, which includes the CUDA and cuDNN libraries TensorFlow needs. If you still see "Could not find cuda drivers" or "Error loading CUDA libraries" despite `nvidia-smi` working in the container, ensure your host driver is compatible with the CUDA version bundled in that image (see [TensorFlow GPU support](https://www.tensorflow.org/install/pip#linux)); very new drivers are usually backward compatible. The app will fall back to CPU if GPU is unavailable.
