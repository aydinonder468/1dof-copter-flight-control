"""
main.py - Application entry point for the Primary Flight Display.

Run with::

    python main.py                                    # mock telemetry (default)
    python main.py --tcp                              # MATLAB TCP at 127.0.0.1:5005
    python main.py --tcp --host 10.0.0.5 --port 6000 # custom TCP endpoint
    python main.py --serial                           # STM32 on COM3 at 115200
    python main.py --serial --serial-port COM5 --baud 921600

The GUI is identical in all modes.  Only the telemetry data source
differs.
"""

from __future__ import annotations

import sys
import argparse

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from main_window import PFDMainWindow


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Aircraft Primary Flight Display")
    # ── Mock (default, no flag needed) ──────────────────────────────────

    # ── TCP mode ─────────────────────────────────────────────────────────
    p.add_argument(
        "--tcp",
        action="store_true",
        help="Use TCP telemetry client instead of mock data",
    )
    p.add_argument("--host", default="127.0.0.1", help="TCP server host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=5005, help="TCP server port (default: 5005)")

    # ── Serial mode ──────────────────────────────────────────────────────
    p.add_argument(
        "--serial",
        action="store_true",
        help="Use serial telemetry client (STM32 FC) instead of mock data",
    )
    p.add_argument(
        "--serial-port",
        default="COM3",
        help="Serial port for STM32 FC (default: COM3; Linux: /dev/ttyUSB0)",
    )
    p.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # consistent cross-platform look

    window = PFDMainWindow()

    # ── Swap telemetry source if --tcp requested ───────────────────────────
    if args.tcp:
        window._connection_type = "TCP"
        window._tcp_host = args.host
        window._tcp_port = args.port
        window._status.set_connection_type("TCP")
        window._switch_telemetry("TCP")

    # ── Swap telemetry source if --serial requested ────────────────────────
    elif args.serial:
        window._connection_type = "SERIAL"
        window._serial_port = args.serial_port
        window._baud = args.baud
        window._status.set_connection_type("SERIAL")
        window._status.set_serial_port(args.serial_port)
        window._switch_telemetry("SERIAL")

    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
