#!/usr/bin/env python3
"""Script to start and stop Docker containers for the armor selection system."""

import subprocess
import sys
import os
from pathlib import Path


def check_docker():
    """Check if Docker is available."""
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_compose_files(no_gpu=False):
    """Get paths to docker-compose files for dev mode.
    If no_gpu is True, include docker-compose.cpu.yml so the task service runs without GPU (12 GB RAM).
    """
    script_dir = Path(__file__).parent
    docker_dir = script_dir / "docker"
    base = (docker_dir / "docker-compose.yml").absolute()
    dev = (docker_dir / "docker-compose.dev.yml").absolute()
    files = [base, dev]
    if no_gpu:
        cpu_file = (docker_dir / "docker-compose.cpu.yml").absolute()
        if cpu_file.exists():
            files.append(cpu_file)
    return files


def get_project_root():
    """Get the project root directory (where docker-compose.yml context should be)."""
    return Path(__file__).parent


def start_containers(build=False, no_gpu=False):
    """Start all Docker containers in dev mode (API hot-reload, source mounted).

    By default, images are only built if missing (fast restarts). Pass --build to
    force a rebuild after changing Dockerfiles or requirements.
    Pass no_gpu=True to run the task container without GPU (12 GB RAM limit).
    """
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        print("  Please install Docker and Docker Compose to continue.")
        sys.exit(1)

    compose_files = get_compose_files(no_gpu=no_gpu)
    for f in compose_files[:2]:
        if not f.exists():
            print(f"✗ ERROR: compose file not found at {f}")
            sys.exit(1)
    if no_gpu and len(compose_files) == 3 and not compose_files[2].exists():
        print(f"✗ ERROR: docker-compose.cpu.yml not found at {compose_files[2]}")
        sys.exit(1)

    print("Starting Docker containers (dev mode)...")
    for f in compose_files:
        print(f"  {f}")
    if no_gpu:
        print("  Task: no GPU, 12 GB RAM limit")
    if build:
        print("  Build: forcing image rebuild")
    else:
        print("  Build: only if images are missing (use --build to force rebuild)")
    print("\n  API: http://localhost:8000  (hot-reload on)")
    print("  Data: ./data is mounted writable (for Save origin, augmentation output, etc.)")
    print("  Redis: localhost:6379")
    print("  Frontend: disabled in dev — run 'npm run dev' in frontend/ for Vite HMR")
    print("  Stop with Ctrl+C, or run: python start.py stop\n")

    try:
        project_root = get_project_root()
        os.chdir(project_root)

        cmd = ["docker", "compose"]
        for f in compose_files:
            cmd.extend(["-f", str(f)])
        cmd.append("up")
        if build:
            cmd.append("--build")

        subprocess.run(
            cmd,
            check=True,
            text=True,
        )

        print("✓ Containers stopped (Ctrl+C)")

    except subprocess.CalledProcessError as e:
        print(f"✗ ERROR: Failed to start containers: {e}")
        sys.exit(1)


def stop_containers():
    """Stop all Docker containers. Uses base + dev compose files only (same project, so stack is torn down)."""
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        sys.exit(1)

    compose_files = get_compose_files(no_gpu=False)
    for f in compose_files[:2]:
        if not f.exists():
            print(f"✗ ERROR: compose file not found at {f}")
            sys.exit(1)

    print("Stopping Docker containers...")

    try:
        project_root = get_project_root()
        os.chdir(project_root)

        cmd = ["docker", "compose"]
        for f in compose_files:
            cmd.extend(["-f", str(f)])
        cmd.append("down")

        subprocess.run(
            cmd,
            check=True,
            text=True,
        )

        print("✓ Containers stopped successfully")

    except subprocess.CalledProcessError as e:
        print(f"✗ ERROR: Failed to stop containers: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python start.py [start|stop]")
        print("       python start.py start [--build]   # --build forces image rebuild")
        print("       python start.py start --no-gpu   # task container: no GPU, 12 GB RAM")
        sys.exit(1)

    command = sys.argv[1].lower()
    build = "--build" in sys.argv
    no_gpu = "--no-gpu" in sys.argv

    if command == "start":
        start_containers(build=build, no_gpu=no_gpu)
    elif command == "stop":
        stop_containers()
    else:
        print(f"✗ ERROR: Unknown command '{command}'")
        print("Usage: python start.py [start|stop]")
        print("       python start.py start [--build]   # --build forces image rebuild")
        print("       python start.py start --no-gpu   # task container: no GPU, 12 GB RAM")
        sys.exit(1)


if __name__ == "__main__":
    main()
