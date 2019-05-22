#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import sys 
import os
PKG = 'numpy_tutorial'
import roslib; roslib.load_manifest(PKG)

import rospy
from rospy.numpy_msg import numpy_msg
from rospy_tutorials.msg import Floats
sys.path=[b for b in sys.path if "2.7" not in b]
sys.path.insert(0,os.getcwd())

import habitat
import pickle
import matplotlib.pyplot as plt
import numpy as np

pub = rospy.Publisher('floats', numpy_msg(Floats),queue_size=10)

def example():
    env = habitat.Env(config=habitat.get_config("configs/tasks/pointnav_rgbd.yaml"))

    def transform_callback(data):
        print (rospy.get_name(), "Plant heard %s"%str(data.data))
        vel_zx=np.float32([-0.4,0.4])
        update_position(vel_zx[0],vel_zx[1],1)
        print("position updated")
        
    rospy.init_node('plant_model',anonymous=True)
    rospy.Subscriber('linear_vel_command', numpy_msg(Floats), transform_callback)

    print("Environment creation successful")
    observations = env.reset()

    print("Agent stepping around inside environment.")
    count_steps = 0

    _x_axis = 0
    _y_axis = 1
    _z_axis = 2

    def update_position(vz, vx, dt):
        """ update agent position in xz plane given velocity and delta time"""
        ax = env._sim._sim.agents[0].scene_node.absolute_transformation()[0:3, _z_axis]
        env._sim._sim.agents[0].scene_node.translate_local(ax * vz * dt)

        ax = env._sim._sim.agents[0].scene_node.absolute_transformation()[0:3, _x_axis]
        env._sim._sim.agents[0].scene_node.translate_local(ax * vx * dt)

    def update_attitude(roll, pitch, yaw, dt):
        """ update agent orientation given angular velocity and delta time"""
        ax_roll = np.zeros(3, dtype=np.float32)
        ax_roll[_z_axis] = 1
        env._sim._sim.agents[0].scene_node.rotate_local(np.deg2rad(roll * dt), ax_roll)
        env._sim._sim.agents[0].scene_node.normalize()

        ax_pitch = np.zeros(3, dtype=np.float32)
        ax_pitch[_x_axis] = 1
        env._sim._sim.agents[0].scene_node.rotate_local(
            np.deg2rad(pitch * dt), ax_pitch
        )
        env._sim._sim.agents[0].scene_node.normalize()

        ax_yaw = np.zeros(3, dtype=np.float32)
        ax_yaw[_y_axis] = 1
        env._sim._sim.agents[0].scene_node.rotate_local(np.deg2rad(yaw * dt), ax_yaw)
        env._sim._sim.agents[0].scene_node.normalize()

    
    while not rospy.is_shutdown():
        while not env.episode_over:
            
            # update agent pose
            #update_position(-1, 0, 1)
         
            # get observations (I think get_observations function is being developed by PR #80)
            sim_obs = env._sim._sim.get_sensor_observations()
            observations = env._sim._sensor_suite.get_observations(sim_obs)
            
            to_publish=np.float32(observations["rgb"].ravel())
            pub.publish(np.float32(observations["rgb"].ravel()))
            # plot rgb and depth observation (can save/send np.array sensor output to ROS in the future)
            #plt.imshow(observations["depth"][:, :, 0])
            #plt.imshow(observations["rgb"])
            count_steps += 1
            print(count_steps)
            #print(to_publish)
            rospy.spin()

    print("Episode finished after {} steps.".format(count_steps))


# currently an infinite loop
if __name__ == "__main__":
    example()

