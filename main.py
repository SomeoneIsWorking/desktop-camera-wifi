from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

import cv2
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QR Mac")
        self.resize(920, 700)

        self.capture = cv2.VideoCapture(0)
        self.detector = cv2.QRCodeDetector()
        self.last_payload = ""
        self.current_wifi: WifiConfig | None = None

        self.video_label = QLabel("Starting camera...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(800, 480)
        self.video_label.setStyleSheet(
            "background: #111827; color: #e5e7eb; border-radius: 12px; padding: 16px;"
        )

        self.status_label = QLabel("Point the camera at a QR code.")
        self.payload_text = QTextEdit()
        self.payload_text.setReadOnly(True)
        self.payload_text.setPlaceholderText("Decoded QR payload will appear here.")

        self.wifi_ssid = QLabel("-")
        self.wifi_auth = QLabel("-")
        self.wifi_hidden = QLabel("-")

        self.connect_button = QPushButton("Connect Wi-Fi")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.handle_wifi_connect)

        self.build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        if not self.capture.isOpened():
            self.status_label.setText("Unable to open the default camera.")

    def build_ui(self) -> None:
        wifi_group = QGroupBox("Wi-Fi QR")
        wifi_form = QFormLayout()
        wifi_form.addRow("SSID", self.wifi_ssid)
        wifi_form.addRow("Auth", self.wifi_auth)
        wifi_form.addRow("Hidden", self.wifi_hidden)
        wifi_group.setLayout(wifi_form)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.connect_button)
        controls_layout.addStretch(1)

        root = QVBoxLayout()
        root.addWidget(self.video_label)
        root.addWidget(self.status_label)
        root.addWidget(self.payload_text)
        root.addWidget(wifi_group)
        root.addLayout(controls_layout)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def update_frame(self) -> None:
        if not self.capture.isOpened():
            return

        ok, frame = self.capture.read()
        if not ok:
            self.status_label.setText("Camera frame read failed.")
            return

        payload, points, _ = self.detector.detectAndDecode(frame)
        if points is not None and len(points) > 0:
            vertices = points.astype(int).reshape(-1, 2)
            for index in range(len(vertices)):
                start = tuple(vertices[index])
                end = tuple(vertices[(index + 1) % len(vertices)])
                cv2.line(frame, start, end, (0, 200, 0), 3)

        self.render_frame(frame)

        if payload and payload != self.last_payload:
            self.last_payload = payload
            self.handle_payload(payload)

    def render_frame(self, frame) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        bytes_per_line = channels * width
        image = QImage(
            rgb_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )
        scaled = QPixmap.fromImage(image).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

    def handle_payload(self, payload: str) -> None:
        self.payload_text.setPlainText(payload)
        wifi_config = parse_wifi_qr(payload)
        self.current_wifi = wifi_config

        if wifi_config is None:
            self.status_label.setText("QR code detected.")
            self.wifi_ssid.setText("-")
            self.wifi_auth.setText("-")
            self.wifi_hidden.setText("-")
            self.connect_button.setEnabled(False)
            return

        self.wifi_ssid.setText(wifi_config.ssid)
        self.wifi_auth.setText(wifi_config.auth_type)
        self.wifi_hidden.setText("Yes" if wifi_config.hidden else "No")
        self.connect_button.setEnabled(True)
        self.status_label.setText("Wi-Fi QR detected. Review and connect if desired.")

    def handle_wifi_connect(self) -> None:
        if self.current_wifi is None:
            return

        config = self.current_wifi
        result = QMessageBox.question(
            self,
            "Connect Wi-Fi",
            f"Join Wi-Fi network '{config.ssid}'?",
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        success, message = connect_to_wifi(config)
        if success:
            QMessageBox.information(self, "Wi-Fi", message)
            self.status_label.setText(message)
            return

        QMessageBox.critical(self, "Wi-Fi", message)
        self.status_label.setText(message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.timer.stop()
        if self.capture.isOpened():
            self.capture.release()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())