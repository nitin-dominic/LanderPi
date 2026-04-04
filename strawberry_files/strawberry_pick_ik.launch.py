import os
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription, LaunchService
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, OpaqueFunction

def launch_setup(context):
    compiled = os.environ['need_compile']
    start = LaunchConfiguration('start', default='true')
    start_arg = DeclareLaunchArgument('start', default_value=start)
    conf = LaunchConfiguration('conf', default=0.45)
    conf_arg = DeclareLaunchArgument('conf', default_value=conf)

    if compiled == 'True':
        controller_package_path = get_package_share_directory('controller')
        peripherals_package_path = get_package_share_directory('peripherals')
        kinematics_package_path = get_package_share_directory('kinematics')
    else:
        controller_package_path = '/home/ubuntu/ros2_ws/src/driver/controller'
        peripherals_package_path = '/home/ubuntu/ros2_ws/src/peripherals'
        kinematics_package_path = '/home/ubuntu/ros2_ws/src/driver/kinematics'

    # Depth camera (provides RGB + depth + camera_info topics)
    depth_camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(peripherals_package_path, 'launch/depth_camera.launch.py')),
    )

    # Controller (servo controller manager)
    controller_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(controller_package_path, 'launch/controller.launch.py')),
    )

    # Kinematics node (converts 3D coordinates to servo angles via IK)
    kinematics_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(kinematics_package_path, 'launch/kinematics_node.launch.py')),
    )

    # YOLO detection node (loads strawberry.xml OpenVINO model)
    yolov11_node = Node(
        package='yolov11_detect',
        executable='yolov11_node',
        output='screen',
        parameters=[
            {'classes': ['ripe', 'unripe']},
            {'model': 'strawberry', 'conf': conf},
            {'start': True},
        ]
    )

    # Strawberry pick IK node (subscribes to YOLO + depth, uses IK to grab)
    strawberry_pick_ik_node = Node(
        package='example',
        executable='strawberry_pick_ik',
        output='screen',
        parameters=[{'start': start}],
    )

    return [
        start_arg,
        conf_arg,
        depth_camera_launch,
        controller_launch,
        kinematics_launch,
        yolov11_node,
        strawberry_pick_ik_node,
    ]

def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])

if __name__ == '__main__':
    ld = generate_launch_description()
    ls = LaunchService()
    ls.include_launch_description(ld)
    ls.run()
