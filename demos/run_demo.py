#!/usr/bin/env python3
"""
AgentConnect Demo Runner

This script manages the startup of both frontend and backend services for the AgentConnect demo.
It provides options to run services individually or together, with configurable host and port settings.

Usage:
    python run_demo.py                     # Run both frontend and backend
    python run_demo.py --backend-only      # Run only backend
    python run_demo.py --frontend-only     # Run only frontend
    python run_demo.py --host 0.0.0.0      # Run with custom host
    python run_demo.py --port 8080         # Run with custom port
"""

import os
import sys
import argparse
import subprocess
import psutil
import atexit
import signal

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import our modules
from demos.utils.demo_logger import setup_logger
from demos.utils.config_manager import get_config
from demos.api.chat_server import run_app

# Set up logger after imports
logger = setup_logger("run_demo", "INFO")
config = get_config()

# Global state
running_processes = set()


def cleanup_processes():
    """Clean up any running processes"""
    for proc in running_processes.copy():
        try:
            if proc.poll() is None:  # Process is still running
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as e:
            logger.error(f"Error cleaning up process: {str(e)}")
    running_processes.clear()


def handle_signal(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received, cleaning up...")
    cleanup_processes()


def check_port_available(port: int) -> bool:
    """Check if a port is available"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True
    except Exception as e:
        logger.error(f"Error checking port availability: {str(e)}")
        return False


def find_process_on_port(port: int) -> int:
    """Find process ID using a specific port"""
    for proc in psutil.process_iter(["pid", "name", "connections"]):
        try:
            for conn in proc.net_connections():
                if conn.laddr.port == port:
                    return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def run_frontend():
    """Run the frontend development server"""
    try:
        frontend_dir = os.path.join(project_root, "demos", "ui", "frontend")
        if not os.path.exists(frontend_dir):
            logger.error(f"Frontend directory not found: {frontend_dir}")
            return None

        logger.info("Starting frontend development server...")
        process = subprocess.Popen(
            ["npm", "run", "dev"], cwd=frontend_dir, shell=True  # Required for Windows
        )
        running_processes.add(process)
        return process
    except Exception as e:
        logger.error(f"Failed to start frontend: {str(e)}")
        return None


def run_backend(host: str, port: int):
    """Run the backend server"""
    try:
        # Temporarily unregister our signal handlers while running uvicorn
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.default_int_handler)

        run_app(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Backend shutdown requested...")
    except Exception as e:
        logger.error(f"Failed to start backend: {str(e)}")
        sys.exit(1)
    finally:
        # Re-register our signal handlers
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        cleanup_processes()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run the AgentConnect demo")
    parser.add_argument(
        "--backend-only", action="store_true", help="Run only the backend server"
    )
    parser.add_argument(
        "--frontend-only", action="store_true", help="Run only the frontend server"
    )
    parser.add_argument("--host", type=str, help="Backend host address")
    parser.add_argument("--port", type=int, help="Backend port number")

    args = parser.parse_args()

    # Load configuration
    config = get_config()

    # Set host and port
    host = args.host or config.api_settings["host"]
    port = args.port or config.api_settings["port"]

    # Register cleanup handlers
    atexit.register(cleanup_processes)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        if args.frontend_only:
            frontend_process = run_frontend()
            if not frontend_process:
                sys.exit(1)
            frontend_process.wait()
        elif args.backend_only:
            run_backend(host, port)
        else:
            # Run both frontend and backend
            frontend_process = run_frontend()
            if frontend_process:
                run_backend(host, port)
            else:
                logger.error("Failed to start frontend. Starting backend only...")
                run_backend(host, port)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running demo: {str(e)}")
    finally:
        cleanup_processes()


if __name__ == "__main__":
    main()
