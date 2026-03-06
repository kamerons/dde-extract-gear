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


def get_compose_file():
    """Get the path to docker-compose.yml."""
    script_dir = Path(__file__).parent
    compose_file = script_dir / "docker" / "docker-compose.yml"
    return compose_file.absolute()


def get_project_root():
    """Get the project root directory (where docker-compose.yml context should be)."""
    script_dir = Path(__file__).parent
    # Go up from armor_select/ to repo root
    return script_dir.parent


def start_containers():
    """Start all Docker containers."""
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        print("  Please install Docker and Docker Compose to continue.")
        sys.exit(1)

    compose_file = get_compose_file()
    if not compose_file.exists():
        print(f"✗ ERROR: docker-compose.yml not found at {compose_file}")
        sys.exit(1)

    print("Starting Docker containers...")
    print(f"Using compose file: {compose_file}")

    try:
        # Change to project root (where docker-compose.yml context should be)
        project_root = get_project_root()
        os.chdir(project_root)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "--build"],
            check=True,
            text=True
        )

        print("✓ Containers started successfully")
        print("\nServices:")
        print("  - Frontend: http://localhost:3000")
        print("  - API: http://localhost:8000")
        print("  - Redis: localhost:6379")
        print("\nTo view logs: docker compose -f docker/docker-compose.yml logs -f")
        print("To stop: python start.py stop")

    except subprocess.CalledProcessError as e:
        print(f"✗ ERROR: Failed to start containers: {e}")
        sys.exit(1)


def stop_containers():
    """Stop all Docker containers."""
    if not check_docker():
        print("✗ ERROR: Docker is not installed or not available in PATH")
        sys.exit(1)

    compose_file = get_compose_file()
    if not compose_file.exists():
        print(f"✗ ERROR: docker-compose.yml not found at {compose_file}")
        sys.exit(1)

    print("Stopping Docker containers...")

    try:
        # Change to project root (where docker-compose.yml context should be)
        project_root = get_project_root()
        os.chdir(project_root)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down"],
            check=True,
            text=True
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
