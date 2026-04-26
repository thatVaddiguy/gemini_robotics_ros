import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'gemini_robotics_er'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'),
            glob('worlds/*.sdf')),
        (os.path.join('share', package_name, 'models', 'parallel_jaw_gripper'),
            glob('models/parallel_jaw_gripper/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vboxuser',
    maintainer_email='rohitvaddi96@gmail.com',
    description='Gemini Robotics-ER 1.6 demo wrapped as ROS 2 nodes with a Gazebo tabletop scene.',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'er_vision_node = gemini_robotics_er.er_vision_node:main',
            'pixel_to_world_node = gemini_robotics_er.pixel_to_world_node:main',
            'hand_controller_node = gemini_robotics_er.hand_controller_node:main',
        ],
    },
)
