from __future__ import annotations

import sys

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

from qr import QRScanner
from wifi import WifiConfig, connect_to_wifi, parse_wifi_qr


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QR Mac")
        self.resize(920, 700)

        self.capture = cv2.VideoCapture()
        self.scanner = QRScanner()
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

        self.retry_timer = QTimer(self)
        self.retry_timer.setInterval(1000)
        self.retry_timer.timeout.connect(self.retry_camera)

        self.retry_camera()

    def set_camera_unavailable(self, status_text: str, video_text: str) -> None:
        self.status_label.setText(status_text)
        self.video_label.setText(video_text)
        if self.capture.isOpened():
            self.capture.release()
        if not self.retry_timer.isActive():
            self.retry_timer.start()

    def retry_camera(self) -> None:
        if self.capture.isOpened():
            self.retry_timer.stop()
            return

        self.capture = self.open_camera()
        if self.capture.isOpened():
            self.retry_timer.stop()
            self.status_label.setText("Point the camera at a QR code.")
            self.video_label.setText("")
            return

        self.set_camera_unavailable(
            "Unable to open the default camera.",
            "Unable to open the camera.\nIf permission was just granted, the app will retry automatically.",
        )

    def open_camera(self):
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
        for backend in backends:
            capture = cv2.VideoCapture(0, backend)
            if capture.isOpened():
                return capture
            capture.release()
        return cv2.VideoCapture()

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
            self.set_camera_unavailable(
                "Camera frame read failed.",
                "Camera opened but no frames arrived.\nThe app will keep retrying automatically.",
            )
            return

        payload, points = self.scanner.detect(frame)
        self.scanner.draw_outline(frame, points)
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
