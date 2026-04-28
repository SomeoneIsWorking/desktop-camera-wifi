from __future__ import annotations

import cv2


class QRScanner:
    def __init__(self) -> None:
        self.detector = cv2.QRCodeDetector()

    def detect(self, frame):
        payload, points, _ = self.detector.detectAndDecode(frame)
        return payload, points

    def draw_outline(self, frame, points) -> None:
        if points is None or len(points) == 0:
            return

        vertices = points.astype(int).reshape(-1, 2)
        for index in range(len(vertices)):
            start = tuple(vertices[index])
            end = tuple(vertices[(index + 1) % len(vertices)])
            cv2.line(frame, start, end, (0, 200, 0), 3)
