from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass
class WifiConfig:
    ssid: str
    password: str
    auth_type: str
    hidden: bool


def unescape_wifi_value(value: str) -> str:
    result: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            result.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            result.append(char)
    if escaped:
        result.append("\\")
    return "".join(result)


def split_wifi_tokens(payload: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    escaped = False
    for char in payload:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == ";":
            tokens.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def parse_wifi_qr(payload: str) -> WifiConfig | None:
    if not payload.startswith("WIFI:"):
        return None

    fields: dict[str, str] = {}
    for token in split_wifi_tokens(payload[5:]):
        if not token or ":" not in token:
            continue
        key, value = token.split(":", 1)
        fields[key] = unescape_wifi_value(value)

    ssid = fields.get("S", "")
    if not ssid:
        return None

    return WifiConfig(
        ssid=ssid,
        password=fields.get("P", ""),
        auth_type=fields.get("T", "nopass") or "nopass",
        hidden=fields.get("H", "false").lower() == "true",
    )


def get_airport_device() -> str:
    result = subprocess.run(
        ["networksetup", "-listallhardwareports"],
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"Hardware Port: Wi-Fi\nDevice: (.+)", result.stdout)
    if not match:
        raise RuntimeError("Could not find the macOS Wi-Fi device.")
    return match.group(1).strip()


def connect_to_wifi(config: WifiConfig) -> tuple[bool, str]:
    try:
        device = get_airport_device()
    except (subprocess.CalledProcessError, RuntimeError) as error:
        return False, str(error)

    command = ["networksetup", "-setairportnetwork", device, config.ssid]
    if config.auth_type.lower() != "nopass" and config.password:
        command.append(config.password)

    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or str(error)
        return False, message

    return True, f"Joined Wi-Fi network '{config.ssid}'."
