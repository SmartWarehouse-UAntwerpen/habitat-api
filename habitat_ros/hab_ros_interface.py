#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import rospy
from rospy.numpy_msg import numpy_msg
from rospy_tutorials.msg import Floats
from geometry_msgs.msg import Twist,Pose,PoseStamped
from std_msgs.msg import Header

import threading
import sys

sys.path = [
    b for b in sys.path if "2.7" not in b
]  # remove path's related to ROS from environment or else certain packages like cv2 can't be imported

import habitat
import habitat_sim.bindings as hsim
import magnum as mn
import numpy as np
import time
import cv2
from habitat.utils.visualizations.maps import COORDINATE_MIN, COORDINATE_MAX

lock = threading.Lock()
rospy.init_node("habitat", anonymous=False)


class sim_env(threading.Thread):

    _x_axis = 0
    _y_axis = 1
    _z_axis = 2
    _dt = 0.00478
    _sensor_rate = 50  # hz
    _r = rospy.Rate(_sensor_rate)

    def __init__(self, env_config_file):
        threading.Thread.__init__(self)
        config = habitat.get_config(config_paths=env_config_file)
        config.defrost()
        config.TASK.MEASUREMENTS.append("TOP_DOWN_MAP")
        config.TASK.SENSORS.append("HEADING_SENSOR")
        config.freeze()

        self.env = habitat.Env(config=config)
        
        # always assume height equals width
        self._sensor_resolution = {
            "RGB": self.env._sim.config["RGB_SENSOR"]["HEIGHT"],
            "DEPTH": self.env._sim.config["DEPTH_SENSOR"]["HEIGHT"],
        }
        self.env._sim._sim.agents[0].move_filter_fn = self.env._sim._sim._step_filter
        self.observations = self.env.reset()

        self.env._sim._sim.agents[0].state.velocity = np.float32([0, 0, 0])
        self.env._sim._sim.agents[0].state.angular_velocity = np.float32([0, 0, 0])

        self._pub_rgb = rospy.Publisher("~rgb", numpy_msg(Floats), queue_size=1)
        self._pub_depth = rospy.Publisher("~depth", numpy_msg(Floats), queue_size=1)
        self._pub_depth_and_pointgoal = rospy.Publisher(
            "depth_and_pointgoal", numpy_msg(Floats), queue_size=1
        )
        self._pub_pose = rospy.Publisher('~pose', PoseStamped, queue_size=1)
        print("created habitat_plant succsefully")

    def _render(self):
        self.env._update_step_stats()  # think this increments episode count
        sim_obs = self.env._sim._sim.get_sensor_observations()
        self.observations = self.env._sim._sensor_suite.get_observations(sim_obs)
        self.observations.update(
            self.env._task.sensor_suite.get_observations(
                observations=self.observations, episode=self.env.current_episode
            )
        )
        self.env._task.measurements.update_measures(
            episode=self.env.current_episode,action=987
        )#action is a dummy value and is not important for this purpose

    def _update_position(self):
        state = self.env.sim.get_agent_state(0)
        vz = -state.velocity[0]
        vx = state.velocity[1]
        dt = self._dt

        start_pos = self.env._sim._sim.agents[0].scene_node.absolute_translation

        ax = (
            self.env._sim._sim.agents[0]
            .scene_node.absolute_transformation()[self._z_axis]
            .xyz
        )
        self.env._sim._sim.agents[0].scene_node.translate_local(ax * vz * dt)

        ax = (
            self.env._sim._sim.agents[0]
            .scene_node.absolute_transformation()[self._x_axis]
            .xyz
        )
        self.env._sim._sim.agents[0].scene_node.translate_local(ax * vx * dt)

        end_pos = self.env._sim._sim.agents[0].scene_node.absolute_translation
        filter_end = self.env._sim._sim.agents[0].move_filter_fn(start_pos, end_pos)
        # Update the position to respect the filter
        self.env._sim._sim.agents[0].scene_node.translate(filter_end - end_pos)
        # self._render()

    def _update_attitude(self):
        """ update agent orientation given angular velocity and delta time"""
        state = self.env.sim.get_agent_state(0)
        yaw = state.angular_velocity[2] / 3.1415926 * 180
        dt = self._dt

        _rotate_local_fns = [
            hsim.SceneNode.rotate_x_local,
            hsim.SceneNode.rotate_y_local,
            hsim.SceneNode.rotate_z_local,
        ]
        _rotate_local_fns[self._y_axis](
            self.env._sim._sim.agents[0].scene_node, mn.Deg(yaw * dt)
        )
        self.env._sim._sim.agents[0].scene_node.rotation = self.env._sim._sim.agents[
            0
        ].scene_node.rotation.normalized()
        # self._render()

    def run(self):
        """Publish sensor readings through ROS on a different thread.
            This method defines what the thread does when the start() method
            of the threading class is called
        """
        while not rospy.is_shutdown():
            lock.acquire()
            h = Header()
            h.stamp = rospy.Time.now()
            h.frame_id = "odom"
            p = Pose()
            hab_pos = self.env._sim._sim.agents[0].state.position
            hab_rot = self.env._sim._sim.agents[0].state.rotation
            #print(hab_rot.x)
            
            print(self.env.get_metrics()['top_down_map'])
            agent_map_coord = self.env.get_metrics()['top_down_map']['agent_map_coord']
            print('got agent_map_coord')
            map_resolution = self.env._config['TASK']['TOP_DOWN_MAP']['MAP_RESOLUTION']
            print(map_resolution)
            agent_map_coord = self.env.get_metrics()['top_down_map']['agent_map_coord']

            p.position.x = -agent_map_coord[1]*(COORDINATE_MAX-COORDINATE_MIN)/map_resolution#-hab_pos[2]
            p.position.y = -agent_map_coord[0]*(COORDINATE_MAX-COORDINATE_MIN)/map_resolution#-hab_pos[0]
            p.position.z = 0 #hab_pos[1]

            p.orientation.x = -hab_rot.z
            p.orientation.y = -hab_rot.x
            p.orientation.z = hab_rot.y
            p.orientation.w = hab_rot.w

            ps = PoseStamped()
            ps.header = h
            ps.pose = p
            self._pub_pose.publish(ps)

            rgb_with_res = np.concatenate(
                (
                    np.float32(self.observations["rgb"].ravel()),
                    np.array(
                        [self._sensor_resolution["RGB"], self._sensor_resolution["RGB"]]
                    ),
                )
            )

            # multiply by 10 to get distance in meters
            depth_with_res = np.concatenate(
                (
                    np.float32(self.observations["depth"].ravel() * 10),
                    np.array(
                        [
                            self._sensor_resolution["DEPTH"],
                            self._sensor_resolution["DEPTH"],
                        ]
                    ),
                )
            )

            depth_np = np.float32(self.observations["depth"].ravel())
            pointgoal_np = np.float32(self.observations["pointgoal"].ravel())
            lock.release()

            self._pub_rgb.publish(np.float32(rgb_with_res))
            self._pub_depth.publish(np.float32(depth_with_res))

            depth_pointgoal_np = np.concatenate((depth_np, pointgoal_np))
            self._pub_depth_and_pointgoal.publish(np.float32(depth_pointgoal_np))
            self._r.sleep()

    def set_linear_velocity(self, vx, vy):
        self.env._sim._sim.agents[0].state.velocity[0] = vx
        self.env._sim._sim.agents[0].state.velocity[1] = vy

    def set_yaw(self, yaw):
        self.env._sim._sim.agents[0].state.angular_velocity[2] = yaw

    def update_orientation(self):
        lock.acquire()
        self._update_attitude()
        self._update_position()
        self._render()
        lock.release()

    def set_dt(self, dt):
        self._dt = dt


def callback(vel, my_env):
    lock.acquire()
    my_env.set_linear_velocity(vel.linear.x, vel.linear.y)
    my_env.set_yaw(vel.angular.z)
    lock.release()


def main():

    my_env = sim_env(env_config_file="configs/tasks/pointnav_rgbd.yaml")
    my_env._render()
    # start the thread that publishes sensor readings
    my_env.start()

    rospy.Subscriber("/cmd_vel", Twist, callback, (my_env), queue_size=1)
    # define a list capturing how long it took
    # to update agent orientation for past 3 instances
    # TODO modify dt_list to depend on r1
    dt_list = [0.009, 0.009, 0.009]
    while not rospy.is_shutdown():
        start_time = time.time()
        # cv2.imshow("bc_sensor", my_env.observations['bc_sensor'])
        # cv2.waitKey(100)
        # time.sleep(0.1)
        my_env.update_orientation()

        dt_list.insert(0, time.time() - start_time)
        dt_list.pop()
        my_env.set_dt(sum(dt_list) / len(dt_list))


if __name__ == "__main__":
    main()
