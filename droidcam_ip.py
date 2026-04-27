#!/usr/bin/env python3
"""Connect to a phone camera through DroidCam by IP and preview the stream.

Usage:
    python droidcam_ip.py 192.168.1.50
    python droidcam_ip.py

If no IP is passed on the command line, the script asks for it interactively.
The default DroidCam URL is http://<ip>:4747/video.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Optional

try:
    import cv2
except ImportError as exc:  # pragma: no cover - depends on local environment
    cv2 = None
    _CV2_IMPORT_ERROR = exc
else:
    _CV2_IMPORT_ERROR = None


DEFAULT_PORT = 4747
DEFAULT_PATH = "/video"
DEFAULT_PHONE_IP = "10.50.112.43"


@dataclass(frozen=True)
class DroidCamConfig:
    ip: str
    port: int = DEFAULT_PORT
    path: str = DEFAULT_PATH

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}{self.path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to a phone through DroidCam using its IP address."
    )
    parser.add_argument("ip", nargs="?", help="Phone IP address on the local network")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="DroidCam port")
    parser.add_argument(
        "--path",
        default=DEFAULT_PATH,
        help="DroidCam stream path (default: /video)",
    )
    return parser.parse_args()


def ask_ip(default_ip: Optional[str] = None) -> str:
    prompt = "Enter the phone IP address"
    if default_ip:
        prompt += f" [{default_ip}]"
    prompt += ": "

    while True:
        value = input(prompt).strip()
        if value:
            return value
        if default_ip:
            return default_ip
        print("IP address cannot be empty.")


def open_stream(config: DroidCamConfig):
    if cv2 is None:
        raise RuntimeError(
            "OpenCV is not installed. Install it with: pip install opencv-python"
        ) from _CV2_IMPORT_ERROR

    capture = cv2.VideoCapture(config.url)
    if not capture.isOpened():
        raise RuntimeError(
            f"Could not open DroidCam stream at {config.url}. "
            "Check that DroidCam is running on the phone and the IP is correct."
        )
    return capture


def preview_stream(config: DroidCamConfig) -> None:
    capture = open_stream(config)
    window_name = "DroidCam Preview"

    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("Stream lost or no frame received.")
                break

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main() -> int:
    args = parse_args()
    ip = args.ip or DEFAULT_PHONE_IP
    config = DroidCamConfig(ip=ip, port=args.port, path=args.path)

    print(f"Connecting to {config.url}")
    try:
        preview_stream(config)
    except Exception as exc:
        print(f"Connection error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
