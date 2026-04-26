"""ROS 2 node that runs Gemini Robotics-ER on the latest camera image on demand.

The annotated image topic is a continuous live stream at the camera rate: each
incoming camera frame is republished with the most recent overlay drawn on top.
Triggers update the overlay state; the next published frame picks it up. This
keeps `rqt_image_view` a useful live monitor rather than a one-shot output.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import rclpy
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from dotenv import load_dotenv
from geometry_msgs.msg import Pose, PoseArray
from PIL import Image as PILImage
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import Trigger

from gemini_robotics_er import visualization
from gemini_robotics_er.er_client import GeminiERClient


def _find_workspace_env() -> Path | None:
    """Walk up from this installed file looking for a sibling src/<pkg>/.env."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src").is_dir() and (parent / "install").is_dir():
            candidate = parent / "src" / "gemini_robotics_er" / ".env"
            if candidate.is_file():
                return candidate
            break
    return None


def _load_env():
    candidates = [
        Path.cwd() / ".env",
        Path(get_package_share_directory("gemini_robotics_er")) / ".env",
    ]
    ws_env = _find_workspace_env()
    if ws_env is not None:
        candidates.append(ws_env)
    for candidate in candidates:
        if candidate.is_file():
            load_dotenv(candidate)
            return str(candidate)
    load_dotenv()
    return None


class ERVisionNode(Node):
    def __init__(self):
        super().__init__("er_vision_node")

        env_path = _load_env()
        if env_path:
            self.get_logger().info(f"loaded env from {env_path}")

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("target", "all visible objects")
        self.declare_parameter("trajectory_source", "the apple")
        self.declare_parameter("trajectory_dest", "the basket")
        self.declare_parameter("trajectory_steps", 15)

        self.bridge = CvBridge()
        self.client = GeminiERClient()

        self._lock = threading.Lock()
        self._latest_pil: PILImage.Image | None = None
        self._latest_bgr = None
        self._overlay_boxes: list = []
        self._overlay_points: list = []
        self._overlay_trajectory: list = []

        image_topic = self.get_parameter("image_topic").value
        self.create_subscription(Image, image_topic, self._on_image, 10)

        self.detections_pub = self.create_publisher(
            String, "/gemini_er/detections_json", 10)
        self.points_pub = self.create_publisher(
            PoseArray, "/gemini_er/points", 10)
        self.annotated_pub = self.create_publisher(
            Image, "/gemini_er/annotated_image", 10)

        self.create_service(Trigger, "/gemini_er/detect_objects", self._svc_detect)
        self.create_service(Trigger, "/gemini_er/point_at", self._svc_point)
        self.create_service(Trigger, "/gemini_er/plan_trajectory", self._svc_trajectory)
        self.create_service(Trigger, "/gemini_er/clear_overlay", self._svc_clear)

        self.get_logger().info(
            f"er_vision_node ready (listening on {image_topic}, "
            f"model={self.client.model_id})"
        )

    def _on_image(self, msg: Image):
        """Cache the frame and republish it with current overlays applied."""
        bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        rgb = bgr[:, :, ::-1]
        with self._lock:
            self._latest_pil = PILImage.fromarray(rgb)
            self._latest_bgr = bgr.copy()
            boxes = list(self._overlay_boxes)
            points = list(self._overlay_points)
            traj = list(self._overlay_trajectory)

        annotated = bgr.copy()
        if boxes:
            visualization.draw_boxes(annotated, boxes)
        if points:
            visualization.draw_points(annotated, points)
        if traj:
            visualization.draw_trajectory(annotated, traj)

        out = self.bridge.cv2_to_imgmsg(annotated, encoding="bgr8")
        out.header = msg.header
        self.annotated_pub.publish(out)

    def _grab_pil(self) -> PILImage.Image | None:
        with self._lock:
            return self._latest_pil

    def _publish_points(self, items):
        arr = PoseArray()
        arr.header.stamp = self.get_clock().now().to_msg()
        arr.header.frame_id = "camera_image"
        for it in items:
            pt = it.get("point")
            if not pt or len(pt) != 2:
                continue
            py, px = pt
            pose = Pose()
            pose.position.x = float(px) / 1000.0
            pose.position.y = float(py) / 1000.0
            pose.position.z = 0.0
            pose.orientation.w = 1.0
            arr.poses.append(pose)
        self.points_pub.publish(arr)

    def _set_overlay(self, *, boxes=None, points=None, trajectory=None):
        with self._lock:
            self._overlay_boxes = list(boxes) if boxes is not None else []
            self._overlay_points = list(points) if points is not None else []
            self._overlay_trajectory = list(trajectory) if trajectory is not None else []

    def _svc_detect(self, request, response):
        target = self.get_parameter("target").value
        pil = self._grab_pil()
        if pil is None:
            response.success = False
            response.message = "no image received yet"
            return response
        try:
            result = self.client.detect_objects(pil, query=target)
        except Exception as e:
            response.success = False
            response.message = f"gemini error: {e}"
            return response
        items = result.parsed
        self._set_overlay(boxes=items)
        self.detections_pub.publish(String(data=json.dumps(items)))
        response.success = True
        response.message = f"detections: {len(items)} items"
        return response

    def _svc_point(self, request, response):
        target = self.get_parameter("target").value
        pil = self._grab_pil()
        if pil is None:
            response.success = False
            response.message = "no image received yet"
            return response
        try:
            result = self.client.point_at(pil, query=target)
        except Exception as e:
            response.success = False
            response.message = f"gemini error: {e}"
            return response
        items = result.parsed
        self._set_overlay(points=items)
        self._publish_points(items)
        response.success = True
        response.message = f"points: {len(items)} items"
        return response

    def _svc_trajectory(self, request, response):
        src = self.get_parameter("trajectory_source").value
        dst = self.get_parameter("trajectory_dest").value
        steps = self.get_parameter("trajectory_steps").value
        pil = self._grab_pil()
        if pil is None:
            response.success = False
            response.message = "no image received yet"
            return response
        try:
            result = self.client.plan_trajectory(pil, source=src, dest=dst, n_steps=steps)
        except Exception as e:
            response.success = False
            response.message = f"gemini error: {e}"
            return response
        items = result.parsed
        self._set_overlay(trajectory=items)
        self._publish_points(items)
        response.success = True
        response.message = f"trajectory: {len(items)} items"
        return response

    def _svc_clear(self, request, response):
        self._set_overlay()
        response.success = True
        response.message = "overlay cleared"
        return response


def main():
    rclpy.init()
    node = ERVisionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
