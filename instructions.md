# gemini_robotics_er

ROS 2 wrapper around the Gemini Robotics-ER 1.6 model from the
[google-gemini/robotics-samples](https://github.com/google-gemini/robotics-samples)
notebook, plus a Gazebo Harmonic tabletop scene with a 2-finger parallel-jaw
gripper.

## Prerequisites

- Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic (`gz sim`)
- Python 3.12
- A Gemini API key from <https://aistudio.google.com/app/apikey>

## Setup

```bash
# 1. ROS ↔ Gazebo bridge
sudo apt install ros-jazzy-ros-gz-bridge ros-jazzy-ros-gz-sim

# 2. Python deps (numpy<2 is required: cv_bridge on Jazzy is built against 1.x)
pip install --user --break-system-packages -r ~/ros2_ws/src/gemini_robotics_er/requirements.txt

# 3. API key
cd ~/ros2_ws/src/gemini_robotics_er
cp .env.example .env
# edit .env and paste your key after GEMINI_API_KEY=

# 4. Build
cd ~/ros2_ws
colcon build --packages-select gemini_robotics_er
source install/setup.bash
```

## Run

```bash
ros2 launch gemini_robotics_er gemini_er_demo.launch.py
```

This brings up Gazebo with the tabletop scene, the ROS↔gz bridge, and the
three nodes (`er_vision_node`, `pixel_to_world_node`, `hand_controller_node`).

## Use

In a second terminal, source the workspace and open the live view:

```bash
source ~/ros2_ws/install/setup.bash
ros2 run rqt_image_view rqt_image_view /gemini_er/annotated_image
```

The live feed streams immediately. Triggers (below) overlay results on top of
it and stay visible until you trigger something else or call `clear_overlay`.

In a third terminal:

```bash
# Detect bounding boxes
ros2 param set /er_vision_node target "all objects on the table"
ros2 service call /gemini_er/detect_objects std_srvs/srv/Trigger

# Point at one thing
ros2 param set /er_vision_node target "the red apple"
ros2 service call /gemini_er/point_at std_srvs/srv/Trigger

# Plan + execute pick-and-place (gripper walks the path in Gazebo)
ros2 param set /er_vision_node trajectory_source apple
ros2 param set /er_vision_node trajectory_dest  basket
ros2 service call /gemini_er/plan_trajectory std_srvs/srv/Trigger

# Wipe the overlay
ros2 service call /gemini_er/clear_overlay std_srvs/srv/Trigger
```

> Each `service call` is exactly one Gemini API request. The 15 fps live video
> does no API work between calls.

## Topics & services

| Name | Type | Notes |
|---|---|---|
| `/camera/image_raw` | `sensor_msgs/Image` | Raw camera, ~15 Hz |
| `/gemini_er/annotated_image` | `sensor_msgs/Image` | Live feed with overlays |
| `/gemini_er/points` | `geometry_msgs/PoseArray` | Normalized image-plane points |
| `/gemini_er/path_world` | `nav_msgs/Path` | 3D trajectory in world frame |
| `/gemini_er/detect_objects` | `std_srvs/Trigger` | Run detection with current `target` |
| `/gemini_er/point_at` | `std_srvs/Trigger` | Point at current `target` |
| `/gemini_er/plan_trajectory` | `std_srvs/Trigger` | Plan path from `source` to `dest` |
| `/gemini_er/clear_overlay` | `std_srvs/Trigger` | Clear all overlays |

## Useful parameters

```bash
ros2 param set /er_vision_node target "the red apple"
ros2 param set /er_vision_node trajectory_source apple
ros2 param set /er_vision_node trajectory_dest  basket
ros2 param set /er_vision_node trajectory_steps 12

# If the gripper moves to the wrong side of the table, flip an axis:
ros2 param set /pixel_to_world_node image_x_to_world_x -1.0
ros2 param set /pixel_to_world_node image_y_to_world_y  1.0
```

## If something breaks

- **`no image received yet` from a service** — the camera bridge isn't
  delivering. Check `gz topic -i -t /camera` shows a publisher and
  `ros2 topic hz /camera/image_raw` reports ~15 Hz.
- **Service returns `gemini error: ... API_KEY_INVALID`** — `.env` has a bad
  key. Test in isolation:
  `python3 -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); from google import genai; print(genai.Client(api_key=os.getenv('GEMINI_API_KEY')).models.generate_content(model='gemini-robotics-er-1.6-preview', contents=['hi']).text)"`
- **`NumPy 1.x cannot be run in NumPy 2.x` traceback** — you have NumPy 2 in
  `~/.local/`. Fix:
  `pip install --user --break-system-packages 'numpy<2' --force-reinstall`
- **`ros2 node list` doesn't show `/er_vision_node`** — it crashed at
  startup. Check `~/.ros/log/latest/launch.log` for the exit code, then run
  `ros2 run gemini_robotics_er er_vision_node` standalone to see the
  traceback.
