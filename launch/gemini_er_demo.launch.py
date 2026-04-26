"""Bring up the tabletop world, the bridges, and the three Gemini-ER nodes."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("gemini_robotics_er")
    world_file = os.path.join(pkg_share, "worlds", "tabletop.sdf")
    models_path = os.path.join(pkg_share, "models")

    set_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=models_path + ":" + os.environ.get("GZ_SIM_RESOURCE_PATH", ""),
    )

    gz_sim = ExecuteProcess(
        cmd=["gz", "sim", "-r", "-v", "3", world_file],
        output="screen",
    )

    # The SDF sets <topic>camera</topic>, so Gazebo publishes the image on
    # /camera and the camera_info on /camera_info (sibling, not nested).
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/camera@sensor_msgs/msg/Image[gz.msgs.Image",
            "/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo",
            "/gripper/left_finger_cmd@std_msgs/msg/Float64]gz.msgs.Double",
            "/gripper/right_finger_cmd@std_msgs/msg/Float64]gz.msgs.Double",
        ],
        remappings=[
            ("/camera", "/camera/image_raw"),
            ("/camera_info", "/camera/camera_info"),
        ],
        output="screen",
    )

    er_vision = Node(
        package="gemini_robotics_er",
        executable="er_vision_node",
        output="screen",
    )

    pixel_to_world = Node(
        package="gemini_robotics_er",
        executable="pixel_to_world_node",
        output="screen",
        parameters=[{
            "camera_x": 0.5,
            "camera_y": 0.0,
            "camera_z": 1.5,
            "table_z": 0.75,
            "hover_height": 0.10,
            "frame_id": "world",
            "image_x_to_world_x": 1.0,
            "image_y_to_world_y": -1.0,
        }],
    )

    hand = Node(
        package="gemini_robotics_er",
        executable="hand_controller_node",
        output="screen",
        parameters=[{
            "world_name": "tabletop",
            "model_name": "parallel_jaw_gripper",
            "dwell_seconds": 1.2,
            "approach_height": 0.10,
        }],
    )

    return LaunchDescription([
        set_resource_path, gz_sim, bridge, er_vision, pixel_to_world, hand,
    ])
