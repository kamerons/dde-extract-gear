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


def get_compose_files():
    """Get paths to docker-compose.yml and docker-compose.dev.yml for dev mode."""
    script_dir = Path(__file__).parent
    docker_dir = script_dir / "docker"
    base = (docker_dir / "docker-compose.yml").absolute()
    dev = (docker_dir / "docker-compose.dev.yml").absolute()
    return base, dev


def get_project_root():
    """Get the project root directory (where docker-compose.yml context should be)."""
    return Path(__file__).parent


def start_containers(build=False):
    """Start all Docker containers in dev mode (API hot-reload, source mounted).

    By default, images are only built if missing (fast restarts). Pass --build to
    force a rebuild after changing Dockerfiles or requirements.
    """
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        print("  Please install Docker and Docker Compose to continue.")
        sys.exit(1)

    base_file, dev_file = get_compose_files()
    if not base_file.exists():
        print(f"✗ ERROR: docker-compose.yml not found at {base_file}")
        sys.exit(1)
    if not dev_file.exists():
        print(f"✗ ERROR: docker-compose.dev.yml not found at {dev_file}")
        sys.exit(1)

    print("Starting Docker containers (dev mode)...")
    print(f"  Base: {base_file}")
    print(f"  Dev:  {dev_file}")
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

        cmd = [
            "docker", "compose",
            "-f", str(base_file),
            "-f", str(dev_file),
            "up",
        ]
        if build:
            cmd.append("--build")

        # -f base -f dev: API gets --reload + source mount; foreground so logs are visible
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
    """Stop all Docker containers (must use same compose files as start)."""
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        sys.exit(1)

    base_file, dev_file = get_compose_files()
    if not base_file.exists():
        print(f"✗ ERROR: docker-compose.yml not found at {base_file}")
        sys.exit(1)
    if not dev_file.exists():
        print(f"✗ ERROR: docker-compose.dev.yml not found at {dev_file}")
        sys.exit(1)

    print("Stopping Docker containers...")

    try:
        project_root = get_project_root()
        os.chdir(project_root)

        subprocess.run(
            [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(dev_file),
                "down",
            ],
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
        sys.exit(1)

    command = sys.argv[1].lower()
    build = "--build" in sys.argv

    if command == "start":
        start_containers(build=build)
    elif command == "stop":
        stop_containers()
    else:
        print(f"✗ ERROR: Unknown command '{command}'")
        print("Usage: python start.py [start|stop]")
        print("       python start.py start [--build]   # --build forces image rebuild")
        sys.exit(1)


if __name__ == "__main__":
    main()
