#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="QR Mac"
APP_BUNDLE="$ROOT_DIR/dist/$APP_NAME.app"
TARGET_BUNDLE="/Applications/$APP_NAME.app"
INFO_PLIST="$APP_BUNDLE/Contents/Info.plist"
CAMERA_USAGE_DESCRIPTION="Scan QR codes from the built-in or connected camera and connect to Wi-Fi networks from QR codes."

cd "$ROOT_DIR"

uv sync --group dev

rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR/$APP_NAME.spec"

uv run pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "com.barishamil.qr-mac" \
  main.py

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "Expected app bundle was not created: $APP_BUNDLE" >&2
  exit 1
fi

if [[ ! -f "$INFO_PLIST" ]]; then
  echo "Expected Info.plist was not created: $INFO_PLIST" >&2
  exit 1
fi

/usr/libexec/PlistBuddy -c "Delete :NSCameraUsageDescription" "$INFO_PLIST" >/dev/null 2>&1 || true
/usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string $CAMERA_USAGE_DESCRIPTION" "$INFO_PLIST"

codesign --force --deep --sign - "$APP_BUNDLE"

rm -rf "$TARGET_BUNDLE"
ditto "$APP_BUNDLE" "$TARGET_BUNDLE"

echo "Installed $TARGET_BUNDLE"