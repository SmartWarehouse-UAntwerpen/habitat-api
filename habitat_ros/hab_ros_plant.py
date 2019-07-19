#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import rospy
from rospy.numpy_msg import numpy_msg
from rospy_tutorials.msg import Floats
from geometry_msgs.msg import Twist
import threading
import sys

sys.path = [
    b for b in sys.path if "2.7" not in b
]  # remove path's related to ROS from environment or else certain packages like cv2 can't be imported

import habitat
import numpy as np
import time
import cv2
count =0

lock = threading.Lock()
rospy.init_node("plant_model", anonymous=True)
class sim_env(threading.Thread):

    _x_axis = 0
    _y_axis = 1
    _z_axis = 2
    _dt = 0.00478
    _sensor_rate = 40  # hz
    _r = rospy.Rate(_sensor_rate)


    def __init__(self, env_config_file):
        threading.Thread.__init__(self)
        self.env = habitat.Env(config=habitat.get_config(env_config_file))
        self.env._sim._sim.agents[0].move_filter_fn = self.env._sim._sim._step_filter
        self.observations = self.env.reset()

        self.env._sim._sim.agents[0].state.velocity = np.float32([0, 0, 0])
        self.env._sim._sim.agents[0].state.angular_velocity = np.float32([0, 0, 0])

        self._pub_rgb = rospy.Publisher("rgb", numpy_msg(Floats), queue_size=10)
        self._pub_depth = rospy.Publisher("depth", numpy_msg(Floats), queue_size=10)
        self._pub_pose = rospy.Publisher("agent_pose", numpy_msg(Floats), queue_size=10)
        self._pub_depth_and_pointgoal = rospy.Publisher(
            "depth_and_pointgoal", numpy_msg(Floats), queue_size=10
        )
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

    def _update_position(self):
        state = self.env.sim.get_agent_state(0)
        vz = -state.velocity[0]
        vx = state.velocity[1]
        dt = self._dt

     
        # start_pos = self.env._sim._sim.agents[0].scene_node.absolute_position()
        start_pos = self.env._sim._sim.agents[0].scene_node.absolute_translation


        ax = self.env._sim._sim.agents[0].scene_node.absolute_transformation()[self._z_axis].xyz
        self.env._sim._sim.agents[0].scene_node.translate_local(ax * vz * dt)

        ax = self.env._sim._sim.agents[0].scene_node.absolute_transformation()[self._x_axis].xyz
        self.env._sim._sim.agents[0].scene_node.translate_local(ax * vx * dt)
        end_pos = self.env._sim._sim.agents[0].scene_node.absolute_translation

        filter_end = self.env._sim._sim.agents[0].move_filter_fn(start_pos, end_pos)
        # Update the position to respect the filter
        self.env._sim._sim.agents[0].scene_node.translate(filter_end - end_pos)

        # dist_moved_before_filter = (end_pos - start_pos).dot()
        # dist_moved_after_filter = (filter_end - start_pos).dot()
        #collided = (dist_moved_after_filter + EPS) < dist_moved_before_filter

        # ax = self.env._sim._sim.agents[0].scene_node.absolute_transformation()[
        #     0:3, self._z_axis
        # ]
        # self.env._sim._sim.agents[0].scene_node.translate_local(ax * vz * dt)

        # ax = self.env._sim._sim.agents[0].scene_node.absolute_transformation()[
        #     0:3, self._x_axis
        # ]
        # self.env._sim._sim.agents[0].scene_node.translate_local(ax * vx * dt)

        # end_pos = self.env._sim._sim.agents[0].scene_node.absolute_position()

        # # can apply or not apply filter
        # filter_end = self.env._sim._sim.agents[0].move_filter_fn(start_pos, end_pos)
        # self.env._sim._sim.agents[0].scene_node.translate(filter_end - end_pos)

        #self.env._sim._sim.agents[0].scene_node.translate_local(5)
        self._render()

    def _update_attitude(self):
        """ update agent orientation given angular velocity and delta time"""
        state = self.env.sim.get_agent_state(0)
        roll = state.angular_velocity[0] * 0  # temporarily ban roll and pitch motion
        pitch = state.angular_velocity[1] * 0  # temporarily ban roll and pitch motion
        yaw = state.angular_velocity[2]/3.1415926*180
        dt = self._dt

        ax_roll = np.zeros(3, dtype=np.float32)
        ax_roll[self._z_axis] = 1
        self.env._sim._sim.agents[0].scene_node.rotate_local(
            np.deg2rad(roll * dt), ax_roll
        )
        self.env._sim._sim.agents[0].scene_node.normalize()

        ax_pitch = np.zeros(3, dtype=np.float32)
        ax_pitch[self._x_axis] = 1
        self.env._sim._sim.agents[0].scene_node.rotate_local(
            np.deg2rad(pitch * dt), ax_pitch
        )
        self.env._sim._sim.agents[0].scene_node.normalize()

        ax_yaw = np.zeros(3, dtype=np.float32)
        ax_yaw[self._y_axis] = 1
        self.env._sim._sim.agents[0].scene_node.rotate_local(
            np.deg2rad(yaw * dt), ax_yaw
        )
        self.env._sim._sim.agents[0].scene_node.normalize()
        self._render()

    def run(self):
        global count
        global lock
        """Publish sensor readings through ROS on a different thread.
            This method defines what the thread does when the start() method
            of the threading class is called
        """
        while not rospy.is_shutdown():
            lock.acquire()
            count = count+1
            print(count)
            self._pub_rgb.publish(np.float32(self.observations["rgb"].ravel()))
            #multiply by 10 to get distance in meters
            self._pub_depth.publish(np.float32(self.observations["depth"].ravel()) * 10)

            depth_np = np.float32(self.observations["depth"].ravel())
            pointgoal_np = np.float32(self.observations["pointgoal"].ravel())
            depth_pointgoal_np = np.concatenate((depth_np, pointgoal_np))
            self._pub_depth_and_pointgoal.publish(np.float32(depth_pointgoal_np))

            print("in running")
            lock.release()
            self._r.sleep()
            

    def set_linear_velocity(self, vx, vy):
        self.env._sim._sim.agents[0].state.velocity[0] = vx
        self.env._sim._sim.agents[0].state.velocity[1] = vy

    def set_yaw(self, yaw):
        self.env._sim._sim.agents[0].state.angular_velocity[2] = yaw

    def update_orientation(self):
        #self._update_attitude()
        self._update_position()
        pass

    def set_dt (self,dt):
        self._dt = dt

def callback(vel, my_env):
    my_env.set_linear_velocity(vel.linear.x, vel.linear.y)
    my_env.set_yaw(vel.angular.z)
    print(
        "inside call back args vel is "
        + str(
            np.concatenate(
                (
                    my_env.env._sim._sim.agents[0].state.velocity,
                    my_env.env._sim._sim.agents[0].state.angular_velocity,
                )
            )
        )
    )


def main():
    global lock
    rospy.init_node("plant_model", anonymous=True)

    my_env = sim_env(env_config_file="configs/tasks/pointnav_rgbd.yaml")
    # start the thread that publishes sensor readings
    my_env.start()

    rospy.Subscriber("cmd_vel", Twist, callback, (my_env))
    #define a list capturing how long it took 
    # to update agent orientation for past 3 instances
    dt_list = [0.009, 0.009, 0.009]
    while not rospy.is_shutdown():
        lock.acquire()

        start_time = time.time()
        my_env.update_orientation()
        dt_list.insert(0, time.time()-start_time)
        #print(time.time()-start_time)
        dt_list.pop()
        my_env.set_dt(sum(dt_list) / len(dt_list))
        lock.release()


if __name__ == "__main__":
    main()