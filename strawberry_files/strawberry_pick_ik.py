#!/usr/bin/env python3
# encoding: utf-8
# Strawberry picking using YOLO detection + depth camera + inverse kinematics
# Adapted from track_and_grab.py
import cv2
import math
import time
import rclpy
import queue
import signal
import threading
import numpy as np
import message_filters
from rclpy.node import Node
from std_srvs.srv import SetBool
from sdk import pid, common, fps
from std_srvs.srv import Trigger
from sensor_msgs.msg import Image, CameraInfo
from interfaces.msg import ObjectsInfo
from rclpy.executors import MultiThreadedExecutor
from servo_controller_msgs.msg import ServosPosition
from rclpy.callback_groups import ReentrantCallbackGroup
from kinematics.kinematics_control import set_pose_target
from kinematics_msgs.srv import GetRobotPose, SetRobotPose
from servo_controller.bus_servo_control import set_servo_position


def depth_pixel_to_camera(pixel_coords, depth, intrinsics):
    fx, fy, cx, cy = intrinsics
    px, py = pixel_coords
    x = (px - cx) * depth / fx
    y = (py - cy) * depth / fy
    z = depth
    return np.array([x, y, z])


class YoloTracker:
    """Uses YOLO bounding box center for PID tracking instead of HSV color detection."""

    def __init__(self, target_class='ripe'):
        self.target_class = target_class
        self.pid_yaw = pid.PID(20.5, 1.0, 1.2)
        self.pid_pitch = pid.PID(20.5, 1.0, 1.2)
        self.yaw = 500
        self.pitch = 150
        self.center = None
        self.radius = 0
        self.detected = False

    def update_detection(self, objects):
        """Called when YOLO detection message arrives. Finds the best target detection."""
        best = None
        for obj in objects:
            if obj.class_name == self.target_class:
                cx = (obj.box[0] + obj.box[2]) / 2.0
                cy = (obj.box[1] + obj.box[3]) / 2.0
                w = abs(obj.box[2] - obj.box[0])
                h = abs(obj.box[3] - obj.box[1])
                radius = max(w, h) / 2.0
                if best is None or obj.score > best[3]:
                    best = (cx, cy, radius, obj.score)

        if best is not None:
            self.center = (best[0], best[1])
            self.radius = best[2]
            self.detected = True
        else:
            self.center = None
            self.radius = 0
            self.detected = False

    def track(self, img_w, img_h, result_image):
        """PID tracking to center the camera on the detected strawberry."""
        if not self.detected or self.center is None:
            return (result_image, None, None, 0)

        center_x, center_y = self.center

        # Draw detection on image
        cv2.circle(result_image, (int(center_x), int(center_y)), int(self.radius), (0, 255, 0), 2)
        cv2.putText(result_image, "ripe", (int(center_x) - 20, int(center_y) - int(self.radius) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # PID for yaw (horizontal centering)
        center_x_norm = center_x / img_w
        if abs(center_x_norm - 0.5) > 0.02:
            self.pid_yaw.SetPoint = 0.5
            self.pid_yaw.update(center_x_norm)
            self.yaw = min(max(self.yaw + self.pid_yaw.output, 0), 1000)
        else:
            self.pid_yaw.clear()

        # PID for pitch (vertical centering)
        center_y_norm = center_y / img_h
        if abs(center_y_norm - 0.5) > 0.02:
            self.pid_pitch.SetPoint = 0.5
            self.pid_pitch.update(center_y_norm)
            self.pitch = min(max(self.pitch + self.pid_pitch.output, 100), 720)
        else:
            self.pid_pitch.clear()

        return (result_image, (self.pitch, self.yaw), (center_x, center_y), self.radius)


class StrawberryPickIKNode(Node):
    hand2cam_tf_matrix = [
        [0.0, 0.0, 1.0, -0.101],
        [-1.0, 0.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 0.037],
        [0.0, 0.0, 0.0, 1.0]
    ]

    def __init__(self, name):
        rclpy.init()
        super().__init__(name, allow_undeclared_parameters=True, automatically_declare_parameters_from_overrides=True)
        self.fps = fps.FPS()
        self.moving = False
        self.count = 0
        self.start = False
        self.running = True
        self.last_pitch_yaw = (0, 0)

        self.enable_disp = 1
        signal.signal(signal.SIGINT, self.shutdown)
        self.last_position = (0, 0, 0)
        self.stamp = time.time()

        self.joints_pub = self.create_publisher(ServosPosition, '/servo_controller', 1)

        self.tracker = YoloTracker(target_class='ripe')

        self.get_current_pose_client = self.create_client(GetRobotPose, '/kinematics/get_current_pose')
        self.get_current_pose_client.wait_for_service()
        self.set_pose_target_client = self.create_client(SetRobotPose, '/kinematics/set_pose_target')
        self.set_pose_target_client.wait_for_service()

        self.create_service(Trigger, '~/start', self.start_srv_callback)
        self.create_service(Trigger, '~/stop', self.stop_srv_callback)

        # Subscribe to YOLO detection results
        self.create_subscription(ObjectsInfo, '/yolo_node/object_detect', self.yolo_callback, 1)

        self.image_queue = queue.Queue(maxsize=2)
        self.endpoint = None
        self.start_stamp = time.time() + 3

        self.client = self.create_client(Trigger, '/controller_manager/init_finish')
        self.client.wait_for_service()

        # Subscribe to synchronized RGB + Depth + CameraInfo
        rgb_sub = message_filters.Subscriber(self, Image, '/ascamera/camera_publisher/rgb0/image')
        depth_sub = message_filters.Subscriber(self, Image, '/ascamera/camera_publisher/depth0/image_raw')
        info_sub = message_filters.Subscriber(self, CameraInfo, '/ascamera/camera_publisher/depth0/camera_info')

        sync = message_filters.ApproximateTimeSynchronizer([rgb_sub, depth_sub, info_sub], 3, 0.02)
        sync.registerCallback(self.multi_callback)

        timer_cb_group = ReentrantCallbackGroup()
        self.timer = self.create_timer(0.0, self.init_process, callback_group=timer_cb_group)

    def init_process(self):
        self.timer.cancel()
        # Move arm to initial scanning position
        set_servo_position(self.joints_pub, 1, ((1, 500), (2, 700), (3, 151), (4, 70), (5, 500), (10, 150)))
        time.sleep(1)
        if self.get_parameter('start').value:
            self.start = True
        threading.Thread(target=self.main, daemon=True).start()
        self.create_service(Trigger, '~/init_finish', self.get_node_state)
        self.get_logger().info('\033[1;32m%s\033[0m' % 'Strawberry IK picker started')

    def get_node_state(self, request, response):
        response.success = True
        return response

    def shutdown(self, signum, frame):
        self.running = False
        self.get_logger().info('\033[1;32m%s\033[0m' % "shutdown")
        cv2.destroyAllWindows()
        rclpy.shutdown()
        import sys
        sys.exit(0)

    def start_srv_callback(self, request, response):
        self.get_logger().info('\033[1;32m%s\033[0m' % "start strawberry pick IK")
        self.start = True
        response.success = True
        response.message = "start"
        return response

    def stop_srv_callback(self, request, response):
        self.get_logger().info('\033[1;32m%s\033[0m' % "stop strawberry pick IK")
        self.start = False
        self.moving = False
        self.count = 0
        self.last_pitch_yaw = (0, 0)
        self.last_position = (0, 0, 0)
        set_servo_position(self.joints_pub, 1, ((1, 500), (2, 720), (3, 100), (4, 120), (5, 500), (10, 150)))
        response.success = True
        response.message = "stop"
        return response

    def send_request(self, client, msg):
        future = client.call_async(msg)
        while rclpy.ok():
            if future.done() and future.result():
                return future.result()

    def yolo_callback(self, msg):
        """Receives YOLO detections and updates the tracker."""
        if msg.objects:
            self.tracker.update_detection(msg.objects)
        else:
            self.tracker.detected = False
            self.tracker.center = None

    def multi_callback(self, ros_rgb_image, ros_depth_image, depth_camera_info):
        if self.image_queue.full():
            self.image_queue.get()
        self.image_queue.put((ros_rgb_image, ros_depth_image, depth_camera_info))

    def get_endpoint(self):
        endpoint = self.send_request(self.get_current_pose_client, GetRobotPose.Request()).pose
        self.endpoint = common.xyz_quat_to_mat(
            [endpoint.position.x, endpoint.position.y, endpoint.position.z],
            [endpoint.orientation.w, endpoint.orientation.x, endpoint.orientation.y, endpoint.orientation.z])
        return self.endpoint

    def pick(self, position):
        """Moves arm to target 3D position, grabs, lifts, places, and returns home."""
        if position[2] < 0.2:
            yaw = 80
        else:
            yaw = 30

        # Move arm to target position
        msg = set_pose_target(position, yaw, [-180.0, 180.0], 1.0)
        res = self.send_request(self.set_pose_target_client, msg)
        if res.pulse:
            servo_data = res.pulse
            set_servo_position(self.joints_pub, 1, ((1, servo_data[0]),))
            time.sleep(1)
            set_servo_position(self.joints_pub, 1.5, (
                (1, servo_data[0]), (2, servo_data[1]), (3, servo_data[2]),
                (4, servo_data[3]), (5, servo_data[4])))
            time.sleep(2.5)

        # Close gripper to grab
        set_servo_position(self.joints_pub, 1.0, ((10, 450),))
        time.sleep(1)

        # Lift up slightly
        position[2] += 0.08
        msg = set_pose_target(position, yaw, [-180.0, 180.0], 1.0)
        res = self.send_request(self.set_pose_target_client, msg)
        if res.pulse:
            servo_data = res.pulse
            set_servo_position(self.joints_pub, 1, (
                (1, servo_data[0]), (2, servo_data[1]), (3, servo_data[2]),
                (4, servo_data[3]), (5, servo_data[4])))
            time.sleep(1)

        # Move to safe upright position with object
        set_servo_position(self.joints_pub, 1, ((1, 500), (2, 720), (3, 100), (4, 120), (5, 500), (10, 500)))
        time.sleep(1)

        # Move to placement position (left side)
        set_servo_position(self.joints_pub, 1, ((1, 125), (2, 635), (3, 120), (4, 200), (5, 500)))
        time.sleep(1)
        set_servo_position(self.joints_pub, 1.5, ((1, 125), (2, 325), (3, 267), (4, 290), (5, 500)))
        time.sleep(1.5)

        # Open gripper to release
        set_servo_position(self.joints_pub, 1, ((1, 125), (2, 325), (3, 267), (4, 290), (5, 500), (10, 150)))
        time.sleep(1.5)

        # Return to scanning position
        set_servo_position(self.joints_pub, 1, ((1, 500), (2, 700), (3, 150), (4, 70), (5, 500), (10, 150)))
        time.sleep(2)

        # Reset tracker state for next detection cycle
        self.tracker.yaw = 500
        self.tracker.pitch = 150
        self.tracker.pid_yaw.clear()
        self.tracker.pid_pitch.clear()
        self.stamp = time.time()
        self.moving = False

    def main(self):
        while self.running:
            try:
                ros_rgb_image, ros_depth_image, depth_camera_info = self.image_queue.get(block=True, timeout=1)
            except queue.Empty:
                if not self.running:
                    break
                else:
                    continue
            try:
                rgb_image = np.ndarray(shape=(ros_rgb_image.height, ros_rgb_image.width, 3), dtype=np.uint8, buffer=ros_rgb_image.data)
                depth_image = np.ndarray(shape=(ros_depth_image.height, ros_depth_image.width), dtype=np.uint16, buffer=ros_depth_image.data)
                result_image = np.copy(rgb_image)

                h, w = depth_image.shape[:2]

                sim_depth_image = np.clip(depth_image, 0, 2000).astype(np.float64)
                sim_depth_image = sim_depth_image / 2000.0 * 255.0
                depth_color_map = cv2.applyColorMap(sim_depth_image.astype(np.uint8), cv2.COLORMAP_JET)

                if self.tracker.detected and not self.moving and time.time() > self.start_stamp and self.start:
                    result_image, p_y, center, r = self.tracker.track(w, h, result_image)

                    if p_y is not None:
                        # Move camera servos to track the target
                        set_servo_position(self.joints_pub, 0.02, ((1, int(p_y[1])), (4, int(p_y[0]))))
                        center_x, center_y = center
                        center_x = min(center_x, w)
                        center_y = min(center_y, h)

                        # Stability check: if PID has settled for 2 seconds, proceed to grab
                        if abs(self.last_pitch_yaw[0] - p_y[0]) < 3 and abs(self.last_pitch_yaw[1] - p_y[1]) < 3:
                            if time.time() - self.stamp > 2:
                                self.stamp = time.time()

                                # Get depth at the target center
                                roi = [
                                    max(0, int(center_y) - 5),
                                    min(h, int(center_y) + 5),
                                    max(0, int(center_x) - 5),
                                    min(w, int(center_x) + 5),
                                ]
                                roi_distance = depth_image[roi[0]:roi[1], roi[2]:roi[3]]
                                try:
                                    valid_depths = roi_distance[np.logical_and(roi_distance > 0, roi_distance < 10000)]
                                    dist = round(float(np.mean(valid_depths) / 1000.0), 3)
                                except BaseException as e:
                                    self.get_logger().info('depth error: ' + str(e))
                                    continue
                                if np.isnan(dist):
                                    continue

                                dist += 0.015  # Object radius compensation
                                dist += 0.015  # Error compensation
                                
                                if dist > 0.35: 
                                    self.get_logger().info('Target too far: %3fm - move closer' % dist)
                                    continue

                                # Convert pixel + depth to 3D camera coordinates
                                K = depth_camera_info.k
                                self.get_endpoint()
                                position = depth_pixel_to_camera((center_x, center_y), dist, (K[0], K[4], K[2], K[5]))

                                # RGB-to-depth camera offset compensation
                                position[0] -= 0.01
                                position[1] -= 0.02
                                position[2] += 0.03

                                # Transform to world coordinates via hand-eye calibration
                                pose_end = np.matmul(self.hand2cam_tf_matrix, common.xyz_euler_to_mat(position, (0, 0, 0)))
                                world_pose = np.matmul(self.endpoint, pose_end)
                                pose_t, pose_R = common.mat_to_xyz_euler(world_pose)

                                self.get_logger().info(
                                    '\033[1;32mGrabbing strawberry at: x=%.3f y=%.3f z=%.3f\033[0m' % (pose_t[0], pose_t[1], pose_t[2]))
                                self.stamp = time.time()
                                self.moving = True
                                threading.Thread(target=self.pick, args=(pose_t,)).start()
                        else:
                            self.stamp = time.time()

                        # Display distance info on depth map
                        dist_val = depth_image[min(int(center_y), h - 1), min(int(center_x), w - 1)]
                        if dist_val < 100:
                            txt = "TOO CLOSE !!!"
                        else:
                            txt = "Dist: {}mm".format(dist_val)
                        cv2.circle(result_image, (int(center_x), int(center_y)), 5, (255, 255, 255), -1)
                        cv2.circle(depth_color_map, (int(center_x), int(center_y)), 5, (255, 255, 255), -1)
                        cv2.putText(depth_color_map, txt, (10, 400 - 20), cv2.FONT_HERSHEY_PLAIN, 2.0, (0, 0, 0), 10, cv2.LINE_AA)
                        cv2.putText(depth_color_map, txt, (10, 400 - 20), cv2.FONT_HERSHEY_PLAIN, 2.0, (255, 255, 255), 2, cv2.LINE_AA)
                        self.last_pitch_yaw = p_y
                    else:
                        self.stamp = time.time()

                if self.enable_disp:
                    result_image = np.concatenate([result_image, depth_color_map], axis=1)
                    cv2.imshow("strawberry_pick", result_image)
                    key = cv2.waitKey(1)
                    if key == ord('q') or key == 27:
                        self.running = False

            except Exception as e:
                self.get_logger().info('error: ' + str(e))
        rclpy.shutdown()


def main():
    node = StrawberryPickIKNode('strawberry_pick_ik')
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    executor.spin()
    node.destroy_node()


if __name__ == "__main__":
    main()
