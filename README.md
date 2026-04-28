# QR Mac

Small macOS desktop app that:

- reads QR codes from your camera
- shows the decoded payload
- detects Wi-Fi QR codes
- connects to the Wi-Fi network on macOS via `networksetup`

## Requirements

- macOS
- Python 3.11+
- camera permission granted to your terminal or Python app when prompted

## Setup

```bash
uv sync
uv run main.py
```

## Build macOS app

```bash
./scripts/install_app.sh
```

This script will:

- sync the project with the `dev` dependency group
- build `QR Mac.app` with PyInstaller through `uv`
- inject the required camera usage description into the app bundle plist
- re-sign the bundle after plist changes so macOS privacy prompts work
- copy the built app into `/Applications`

If macOS blocks camera access for the new app bundle, grant permission in System Settings and reopen it from `/Applications`.

## Wi-Fi QR support

The app supports common Wi-Fi QR payloads such as:

```text
WIFI:T:WPA;S:MyNetwork;P:supersecret;H:false;;
```

When a Wi-Fi QR is detected, the app enables a button that runs the macOS command:

```bash
networksetup -setairportnetwork <device> <ssid> <password>
```

If the QR code represents an open network, the password is omitted.

## Notes

- Hidden-network metadata is parsed and shown, but the app does not preconfigure hidden-network profiles.
- If camera access is denied, grant permission in System Settings and restart the app.

## Tooling

This project is set up for `uv`, including dependency resolution and command execution.
