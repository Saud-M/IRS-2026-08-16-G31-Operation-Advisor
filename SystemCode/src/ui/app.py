"""Main Entrypoint for Operation Advisor Operator Cockpit Application.

Usage:
    python3 src/ui/app.py [--port 8501] [--host 127.0.0.1]
    python3 -m src.ui.app

Launches the local, offline, zero-dependency Operator Cockpit dashboard.
"""

import argparse
import os
import sys
import threading
import time
from typing import Optional, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ui.server import start_cockpit_server, COCKPIT_STATE


def run_cockpit_app(port: int = 8501, host: str = "127.0.0.1", blocking: bool = True) -> Any:
    """Launch the Operation Advisor Cockpit server."""
    print("=" * 70)
    print("  OPERATION ADVISOR — DECISION SUPPORT COCKPIT (TRAIN 1)")
    print("  High-Pressure Separator V-101 & Centrifugal Compressor K-101")
    print(f"  Local Web Dashboard: http://{host}:{port}/")
    print("  OSHA 1910.119 PSM & API RP 75 Validated")
    print("=" * 70)

    server = start_cockpit_server(port=port, host=host)

    if blocking:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Operation Advisor Cockpit...")
            server.server_close()
            sys.exit(0)
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Operation Advisor Cockpit Server")
    parser.add_argument("--port", type=int, default=8501, help="Port to bind (default: 8501)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    run_cockpit_app(port=args.port, host=args.host, blocking=True)
