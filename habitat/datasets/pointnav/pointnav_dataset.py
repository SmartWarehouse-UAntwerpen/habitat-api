#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import gzip
import json
import os
from typing import List

from habitat.config import Config
from habitat.core.dataset import Dataset
from habitat.tasks.nav.nav_task import (
    NavigationGoal,
    ShortestPathPoint,
    NavigationEpisode,
)

ALL_SCENES_MASK = "*"
CONTENT_SCENES_PATH_FIELD = "content_scenes_path"


class PointNavDatasetV1(Dataset):
    """
        Class inherited from Dataset that loads Point Navigation dataset.
    """

    episodes: List[NavigationEpisode]
    content_scenes_path: str = "{data_path}/content/{scene}.json.gz"

    @staticmethod
    def check_config_paths_exist(config: Config) -> bool:
        return os.path.exists(
            config.POINTNAVV1.DATA_PATH.format(split=config.SPLIT)
        )

    @staticmethod
    def get_scenes_to_load(config: Config) -> List[str]:
        """Return list of scene ids for which dataset has separate files with
        episodes.
        """
        assert PointNavDatasetV1.check_config_paths_exist(config)
        dataset_dir = os.path.dirname(
            config.POINTNAVV1.DATA_PATH.format(split=config.SPLIT)
        )

        cfg = config.clone()
        cfg.defrost()
        cfg.POINTNAVV1.CONTENT_SCENES = []
        dataset = PointNavDatasetV1(cfg)
        return PointNavDatasetV1._get_scenes_from_folder(
            content_scenes_path=dataset.content_scenes_path,
            dataset_dir=dataset_dir,
        )

    @staticmethod
    def _get_scenes_from_folder(content_scenes_path, dataset_dir):
        scenes = []
        content_dir = content_scenes_path.split("{scene}")[0]
        scene_dataset_ext = content_scenes_path.split("{scene}")[1]
        content_dir = content_dir.format(data_path=dataset_dir)
        if not os.path.exists(content_dir):
            return scenes

        for filename in os.listdir(content_dir):
            if filename.endswith(scene_dataset_ext):
                scene = filename[: -len(scene_dataset_ext)]
                scenes.append(scene)
        scenes.sort()
        return scenes

    def __init__(self, config: Config = None) -> None:
        self.episodes = []

        if config is None:
            return

        datasetfile_path = config.POINTNAVV1.DATA_PATH.format(
            split=config.SPLIT
        )
        with gzip.open(datasetfile_path, "rt") as f:
            self.from_json(f.read())

        # Read separate file for each scene
        dataset_dir = os.path.dirname(datasetfile_path)
        scenes = config.POINTNAVV1.CONTENT_SCENES
        if ALL_SCENES_MASK in scenes:
            scenes = PointNavDatasetV1._get_scenes_from_folder(
                content_scenes_path=self.content_scenes_path,
                dataset_dir=dataset_dir,
            )

        for scene in scenes:
            scene_filename = self.content_scenes_path.format(
                data_path=dataset_dir, scene=scene
            )
            with gzip.open(scene_filename, "rt") as f:
                self.from_json(f.read())

    def from_json(self, json_str: str) -> None:
        deserialized = json.loads(json_str)
        if CONTENT_SCENES_PATH_FIELD in deserialized:
            self.content_scenes_path = deserialized[CONTENT_SCENES_PATH_FIELD]

        for episode in deserialized["episodes"]:
            episode = NavigationEpisode(**episode)
            for g_index, goal in enumerate(episode.goals):
                episode.goals[g_index] = NavigationGoal(**goal)
            if episode.shortest_paths is not None:
                for path in episode.shortest_paths:
                    for p_index, point in enumerate(path):
                        path[p_index] = ShortestPathPoint(**point)
            self.episodes.append(episode)