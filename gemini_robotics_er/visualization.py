"""Draw Gemini ER results on top of an OpenCV BGR image."""
from __future__ import annotations

import cv2
import numpy as np

POINT_COLOR = (0, 255, 0)
BOX_COLOR = (0, 200, 255)
TRAJ_COLOR = (255, 100, 0)


def _denorm(coord: float, dim: int) -> int:
    return int(round(float(coord) / 1000.0 * dim))


def draw_boxes(img: np.ndarray, items: list) -> np.ndarray:
    h, w = img.shape[:2]
    for item in items:
        box = item.get("box_2d")
        label = str(item.get("label", ""))
        if not box or len(box) != 4:
            continue
        ymin, xmin, ymax, xmax = box
        p1 = (_denorm(xmin, w), _denorm(ymin, h))
        p2 = (_denorm(xmax, w), _denorm(ymax, h))
        cv2.rectangle(img, p1, p2, BOX_COLOR, 2)
        cv2.putText(img, label, (p1[0], max(12, p1[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOX_COLOR, 2)
    return img


def draw_points(img: np.ndarray, items: list, color=POINT_COLOR) -> np.ndarray:
    h, w = img.shape[:2]
    for item in items:
        pt = item.get("point")
        label = str(item.get("label", ""))
        if not pt or len(pt) != 2:
            continue
        py, px = pt
        center = (_denorm(px, w), _denorm(py, h))
        cv2.circle(img, center, 6, color, -1)
        cv2.putText(img, label, (center[0] + 8, center[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return img


def draw_trajectory(img: np.ndarray, items: list) -> np.ndarray:
    h, w = img.shape[:2]

    def order_key(it):
        try:
            return int(it.get("label", 0))
        except (ValueError, TypeError):
            return 0

    pts = []
    for item in sorted(items, key=order_key):
        pt = item.get("point")
        if not pt or len(pt) != 2:
            continue
        py, px = pt
        pts.append((_denorm(px, w), _denorm(py, h)))

    for i in range(1, len(pts)):
        cv2.arrowedLine(img, pts[i - 1], pts[i], TRAJ_COLOR, 2, tipLength=0.2)
    for i, p in enumerate(pts):
        cv2.circle(img, p, 4, TRAJ_COLOR, -1)
        cv2.putText(img, str(i), (p[0] + 6, p[1] + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, TRAJ_COLOR, 1)
    return img
