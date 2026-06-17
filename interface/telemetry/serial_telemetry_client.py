"""
serial_telemetry_client.py - Serial telemetry receiver for the STM32 flight
controller.

Protocol v1, little-endian, 65 bytes:

    0      uint8   sync0 = 0xAA
    1      uint8   sync1 = 0x55
    2      uint8   version = 1
    3      uint8   flags: bit0=IMU valid, bit1=barometer valid
    4      uint32  time_ms
    8      float   roll_deg
    12     float   pitch_deg
    16     float   heading_deg
    20     float   altitude_ft
    24     float   vertical_speed_fpm
    28     float   ax_g
    32     float   ay_g
    36     float   az_g
    40     float   gx_dps
    44     float   gy_dps
    48     float   gz_dps
    52     float   pressure_pa
    56     float   imu_temp_c
    60     float   bmp_temp_c
    64     uint8   checksum, XOR of bytes 2..63

The older 15-byte packet (AA 55 + roll/pitch/yaw float32 + checksum) is still
accepted so older firmware does not break the interface.
"""

from __future__ import annotations

import math
import struct
import threading
import time

from PySide6.QtCore import QThread, Signal

from flight_state import FlightData

try:
    import serial
except ImportError:
    serial = None  # type: ignore[assignment]


SYNC_0 = 0xAA
SYNC_1 = 0x55
VERSION_1 = 0x01
VERSION_2 = 0x02

HEADER_SIZE = 2
CHECKSUM_SIZE = 1

LEGACY_PAYLOAD_FMT = "<fff"
LEGACY_PAYLOAD_SIZE = struct.calcsize(LEGACY_PAYLOAD_FMT)
LEGACY_PACKET_SIZE = HEADER_SIZE + LEGACY_PAYLOAD_SIZE + CHECKSUM_SIZE

V1_PAYLOAD_FMT = "<BBI" + ("f" * 14)
V1_PAYLOAD_SIZE = struct.calcsize(V1_PAYLOAD_FMT)
V1_PACKET_SIZE = HEADER_SIZE + V1_PAYLOAD_SIZE + CHECKSUM_SIZE

V2_PAYLOAD_FMT = "<BBI" + ("f" * 21)
V2_PAYLOAD_SIZE = struct.calcsize(V2_PAYLOAD_FMT)
V2_PACKET_SIZE = HEADER_SIZE + V2_PAYLOAD_SIZE + CHECKSUM_SIZE

MIN_PACKET_SIZE = LEGACY_PACKET_SIZE


def _xor_checksum(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


class SerialTelemetryClient(QThread):
    """Reads STM32 telemetry frames from a serial port."""

    new_data = Signal(FlightData)
    connection_status = Signal(str)

    def __init__(
        self,
        port: str = "COM3",
        baud: int = 115200,
        reconnect_delay: float = 2.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._port = port
        self._baud = baud
        self._reconnect_delay = reconnect_delay
        self._running = True
        self.is_armed = False
        self._ser = None
        self._write_lock = threading.Lock()

    def run(self) -> None:
        if serial is None:
            self.connection_status.emit(
                "error: pyserial not installed (pip install pyserial)"
            )
            return

        while self._running:
            try:
                self._open_and_read()
            except serial.SerialException as exc:
                self.connection_status.emit(f"disconnected: {exc}")
                if self._running:
                    time.sleep(self._reconnect_delay)

    def _open_and_read(self) -> None:
        with serial.Serial(
            port=self._port,
            baudrate=self._baud,
            timeout=0.2,
        ) as ser:
            try:
                ser.dtr = True
                ser.rts = True
                with self._write_lock:
                    self._ser = ser
                self.connection_status.emit(f"connected: {self._port} @ {self._baud}")
                buf = bytearray()

                while self._running:
                    chunk = ser.read(256)
                    if not chunk:
                        continue
                    buf.extend(chunk)
                    self._parse_buffer(buf)
            finally:
                with self._write_lock:
                    self._ser = None
        self.connection_status.emit("disconnected")

    def _parse_buffer(self, buf: bytearray) -> None:
        while len(buf) >= MIN_PACKET_SIZE:
            sync_index = self._find_sync(buf)
            if sync_index is None:
                buf.clear()
                return

            if sync_index > 0:
                del buf[:sync_index]

            if len(buf) < MIN_PACKET_SIZE:
                return

            if len(buf) >= 3 and buf[2] == VERSION_2:
                if len(buf) < V2_PACKET_SIZE:
                    return

                pkt = bytes(buf[:V2_PACKET_SIZE])
                del buf[:V2_PACKET_SIZE]
                payload = pkt[HEADER_SIZE : HEADER_SIZE + V2_PAYLOAD_SIZE]
                if pkt[-1] == _xor_checksum(payload):
                    self._decode_v2_payload(payload)
                continue

            if len(buf) >= 3 and buf[2] == VERSION_1:
                if len(buf) < V1_PACKET_SIZE:
                    return

                pkt = bytes(buf[:V1_PACKET_SIZE])
                del buf[:V1_PACKET_SIZE]
                payload = pkt[HEADER_SIZE : HEADER_SIZE + V1_PAYLOAD_SIZE]
                if pkt[-1] == _xor_checksum(payload):
                    self._decode_v1_payload(payload)
                continue

            if len(buf) < LEGACY_PACKET_SIZE:
                return

            pkt = bytes(buf[:LEGACY_PACKET_SIZE])
            del buf[:LEGACY_PACKET_SIZE]
            payload = pkt[HEADER_SIZE : HEADER_SIZE + LEGACY_PAYLOAD_SIZE]
            if pkt[-1] == _xor_checksum(payload):
                self._decode_legacy_payload(payload)

    @staticmethod
    def _find_sync(buf: bytearray) -> int | None:
        for index in range(len(buf) - 1):
            if buf[index] == SYNC_0 and buf[index + 1] == SYNC_1:
                return index
        return None

    @staticmethod
    def _finite(value: float, default: float = 0.0) -> float:
        return value if math.isfinite(value) else default

    def _decode_legacy_payload(self, payload: bytes) -> None:
        try:
            roll, pitch, yaw = struct.unpack(LEGACY_PAYLOAD_FMT, payload)
        except struct.error:
            return

        self.new_data.emit(
            FlightData(
                roll=self._finite(roll),
                pitch=self._finite(pitch),
                heading=self._finite(yaw) % 360.0,
                ground_link="CONNECTED",
                telemetry_status="HEALTHY",
            )
        )

    def _decode_v1_payload(self, payload: bytes) -> None:
        try:
            values = struct.unpack(V1_PAYLOAD_FMT, payload)
        except struct.error:
            return

        (
            version,
            flags,
            _time_ms,
            roll,
            pitch,
            heading,
            altitude_ft,
            vertical_speed_fpm,
            _ax_g,
            _ay_g,
            _az_g,
            _gx_dps,
            _gy_dps,
            _gz_dps,
            _pressure_pa,
            _imu_temp_c,
            _bmp_temp_c,
        ) = values

        if version != VERSION_1:
            return

        imu_valid = bool(flags & 0x01)
        baro_valid = bool(flags & 0x02)
        telemetry_status = "HEALTHY" if imu_valid and baro_valid else "DEGRADED"

        self.new_data.emit(
            FlightData(
                roll=self._finite(roll),
                pitch=self._finite(pitch),
                heading=self._finite(heading) % 360.0,
                airspeed=0.0,
                altitude=max(0.0, self._finite(altitude_ft)),
                vertical_speed=self._finite(vertical_speed_fpm),
                ground_speed=0.0,
                pitot_airspeed=0.0,
                throttle=0.0,
                link_quality=100.0 if imu_valid else 40.0,
                interference=0.0,
                signal_strength=100.0,
                battery_percent=100.0,
                battery_voltage=0.0,
                ground_link="CONNECTED",
                telemetry_status=telemetry_status,
                autopilot_status="MANUAL",
            )
        )

    def _decode_v2_payload(self, payload: bytes) -> None:
        try:
            values = struct.unpack(V2_PAYLOAD_FMT, payload)
        except struct.error:
            return

        (
            version,
            flags,
            _time_ms,
            roll,
            pitch,
            heading,
            altitude_ft,
            vertical_speed_fpm,
            control_ref,
            control_angle,
            control_rate,
            control_error,
            control_u_diff,
            pwm_left,
            pwm_right,
            _ax_g,
            _ay_g,
            _az_g,
            _gx_dps,
            _gy_dps,
            _gz_dps,
            _pressure_pa,
            _imu_temp_c,
            _bmp_temp_c,
        ) = values

        if version != VERSION_2:
            return

        imu_valid = bool(flags & 0x01)
        baro_valid = bool(flags & 0x02)
        armed = bool(flags & 0x04)
        safety_latched = bool(flags & 0x08)
        self.is_armed = armed

        if safety_latched:
            telemetry_status = "ERROR"
        elif imu_valid and baro_valid:
            telemetry_status = "HEALTHY"
        else:
            telemetry_status = "DEGRADED"

        self.new_data.emit(
            FlightData(
                roll=self._finite(roll),
                pitch=self._finite(pitch),
                heading=self._finite(heading) % 360.0,
                airspeed=0.0,
                altitude=max(0.0, self._finite(altitude_ft)),
                vertical_speed=self._finite(vertical_speed_fpm),
                ground_speed=0.0,
                pitot_airspeed=0.0,
                throttle=0.0,
                control_ref=self._finite(control_ref),
                control_angle=self._finite(control_angle),
                control_rate=self._finite(control_rate),
                control_error=self._finite(control_error),
                control_u_diff=self._finite(control_u_diff),
                pwm_left=self._finite(pwm_left, 1000.0),
                pwm_right=self._finite(pwm_right, 1000.0),
                link_quality=100.0 if imu_valid else 40.0,
                interference=0.0,
                signal_strength=100.0,
                battery_percent=100.0,
                battery_voltage=0.0,
                armed=armed,
                ground_link="CONNECTED",
                telemetry_status=telemetry_status,
                autopilot_status="ENGAGED" if armed else "MANUAL",
            )
        )

    def _send_command(self, command: str) -> bool:
        line = (command.strip() + "\n").encode("ascii", errors="ignore")
        with self._write_lock:
            ser = self._ser
            if ser is None or not ser.is_open:
                return False
            ser.write(line)
            ser.flush()
            return True

    def set_armed(self, armed: bool) -> None:
        self.is_armed = armed
        if not self._send_command(f"ARM,{1 if armed else 0}"):
            self.connection_status.emit("warning: serial port not ready for ARM command")

    def set_reference(self, reference_deg: float) -> None:
        self._send_command(f"REF,{reference_deg:.3f}")

    def stop(self) -> None:
        self._running = False
        self.wait(3000)
