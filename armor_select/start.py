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
    script_dir = Path(__file__).parent
    # Go up from armor_select/ to repo root
    return script_dir.parent


def start_containers():
    """Start all Docker containers in dev mode (API hot-reload, source mounted)."""
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
    print("\n  API: http://localhost:8000  (hot-reload on)")
    print("  Redis: localhost:6379")
    print("  Frontend: disabled in dev — run 'npm run dev' in armor_select/frontend for Vite HMR")
    print("  Stop with Ctrl+C, or run: python start.py stop\n")

    try:
        project_root = get_project_root()
        os.chdir(project_root)

        # -f base -f dev: API gets --reload + source mount; foreground so logs are visible
        subprocess.run(
            [
                "docker", "compose",
                "-f", str(base_file),
                "-f", str(dev_file),
                "up", "--build",
            ],
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
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "start":
        start_containers()
    elif command == "stop":
        stop_containers()
    else:
        print(f"✗ ERROR: Unknown command '{command}'")
        print("Usage: python start.py [start|stop]")
        sys.exit(1)


if __name__ == "__main__":
    main()
