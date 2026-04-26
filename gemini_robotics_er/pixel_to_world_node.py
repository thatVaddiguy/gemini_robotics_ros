"""Project normalized image points to 3D world coordinates on the table plane.

Assumes a fixed overhead camera looking straight down (-Z world). Uses the
standard pinhole model from the bridged sensor_msgs/CameraInfo and a
configurable table-Z plane to back-project pixels into world XY.
"""
from __future__ import annotations

import rclpy
from geometry_msgs.msg import PoseArray, PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo


class PixelToWorldNode(Node):
    def __init__(self):
        super().__init__("pixel_to_world_node")

        self.declare_parameter("camera_x", 0.5)
        self.declare_parameter("camera_y", 0.0)
        self.declare_parameter("camera_z", 1.5)
        self.declare_parameter("table_z", 0.75)
        self.declare_parameter("hover_height", 0.10)
        self.declare_parameter("frame_id", "world")
        # Sign flips to align image axes with world axes for our overhead setup.
        self.declare_parameter("image_x_to_world_x", 1.0)
        self.declare_parameter("image_y_to_world_y", -1.0)

        self.camera_info: CameraInfo | None = None
        self.create_subscription(CameraInfo, "/camera/camera_info",
                                 self._on_info, 10)
        self.create_subscription(PoseArray, "/gemini_er/points",
                                 self._on_points, 10)
        self.path_pub = self.create_publisher(Path, "/gemini_er/path_world", 10)

    def _on_info(self, msg: CameraInfo):
        self.camera_info = msg

    def _on_points(self, msg: PoseArray):
        if self.camera_info is None:
            self.get_logger().warn("no camera_info yet, dropping points")
            return

        info = self.camera_info
        fx, fy = info.k[0], info.k[4]
        cx, cy = info.k[2], info.k[5]
        width, height = info.width, info.height
        if fx == 0 or fy == 0 or width == 0 or height == 0:
            self.get_logger().warn("camera_info has zero intrinsics, dropping")
            return

        cam_x = self.get_parameter("camera_x").value
        cam_y = self.get_parameter("camera_y").value
        cam_z = self.get_parameter("camera_z").value
        tab_z = self.get_parameter("table_z").value
        hover = self.get_parameter("hover_height").value
        sx = self.get_parameter("image_x_to_world_x").value
        sy = self.get_parameter("image_y_to_world_y").value
        frame = self.get_parameter("frame_id").value

        depth = cam_z - tab_z
        path = Path()
        path.header.stamp = self.get_clock().now().to_msg()
        path.header.frame_id = frame

        for pose in msg.poses:
            u = pose.position.x * width
            v = pose.position.y * height
            cam_dx = (u - cx) * depth / fx
            cam_dy = (v - cy) * depth / fy
            world_x = cam_x + sx * cam_dx
            world_y = cam_y + sy * cam_dy
            ps = PoseStamped()
            ps.header = path.header
            ps.pose.position.x = world_x
            ps.pose.position.y = world_y
            ps.pose.position.z = tab_z + hover
            ps.pose.orientation.w = 1.0
            path.poses.append(ps)

        self.path_pub.publish(path)
        self.get_logger().info(
            f"published path with {len(path.poses)} waypoints in '{frame}'"
        )


def main():
    rclpy.init()
    node = PixelToWorldNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
