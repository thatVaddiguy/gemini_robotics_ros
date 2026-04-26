"""Drive the floating parallel-jaw gripper through a 3D path.

The gripper base is teleported via the Gazebo `/world/<world>/set_pose`
service (called through the `gz` CLI for portability). The two prismatic
finger joints are driven via std_msgs/Float64 commands bridged into Gazebo.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time

import rclpy
from nav_msgs.msg import Path
from rclpy.node import Node
from std_msgs.msg import Float64


class HandControllerNode(Node):
    def __init__(self):
        super().__init__("hand_controller_node")

        self.declare_parameter("world_name", "tabletop")
        self.declare_parameter("model_name", "parallel_jaw_gripper")
        self.declare_parameter("dwell_seconds", 1.2)
        self.declare_parameter("approach_height", 0.10)
        self.declare_parameter("open_position", 0.04)
        self.declare_parameter("closed_position", 0.005)

        self.create_subscription(Path, "/gemini_er/path_world",
                                 self._on_path, 10)
        self.left_pub = self.create_publisher(
            Float64, "/gripper/left_finger_cmd", 10)
        self.right_pub = self.create_publisher(
            Float64, "/gripper/right_finger_cmd", 10)

        self._busy = threading.Lock()

        if shutil.which("gz") is None:
            self.get_logger().error(
                "`gz` CLI not on PATH; set_pose calls will fail. "
                "Source the Gazebo Harmonic environment."
            )

    def _set_finger(self, opening: float):
        self.left_pub.publish(Float64(data=float(opening)))
        self.right_pub.publish(Float64(data=float(opening)))

    def _set_pose(self, x: float, y: float, z: float):
        world = self.get_parameter("world_name").value
        model = self.get_parameter("model_name").value
        req = (
            f'name: "{model}", '
            f'position: {{x: {x}, y: {y}, z: {z}}}, '
            'orientation: {x: 0, y: 0, z: 0, w: 1}'
        )
        cmd = [
            "gz", "service", "-s", f"/world/{world}/set_pose",
            "--reqtype", "gz.msgs.Pose",
            "--reptype", "gz.msgs.Boolean",
            "--timeout", "1000",
            "--req", req,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            self.get_logger().error(f"set_pose failed: {e.stderr.strip()}")
        except FileNotFoundError:
            self.get_logger().error("`gz` CLI not found")

    def _execute(self, path: Path):
        if not self._busy.acquire(blocking=False):
            self.get_logger().warn("already executing a path, ignoring new one")
            return
        try:
            dwell = self.get_parameter("dwell_seconds").value
            open_p = self.get_parameter("open_position").value
            closed_p = self.get_parameter("closed_position").value
            approach = self.get_parameter("approach_height").value
            n = len(path.poses)
            self.get_logger().info(f"executing path with {n} waypoints")

            self._set_finger(open_p)
            time.sleep(dwell * 0.5)

            for i, ps in enumerate(path.poses):
                x = ps.pose.position.x
                y = ps.pose.position.y
                z = ps.pose.position.z + approach
                self._set_pose(x, y, z)
                time.sleep(dwell)
                if i == 0:
                    # Descend to the table and close (pickup).
                    self._set_pose(x, y, ps.pose.position.z)
                    time.sleep(dwell * 0.5)
                    self._set_finger(closed_p)
                    time.sleep(dwell * 0.5)
                    self._set_pose(x, y, z)
                    time.sleep(dwell * 0.3)

            # Drop at the destination.
            self._set_finger(open_p)
            self.get_logger().info("path execution complete")
        finally:
            self._busy.release()

    def _on_path(self, path: Path):
        if not path.poses:
            return
        # Run on a worker thread so the executor isn't blocked.
        threading.Thread(target=self._execute, args=(path,), daemon=True).start()


def main():
    rclpy.init()
    node = HandControllerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
