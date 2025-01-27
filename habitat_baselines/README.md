baselines
==============================
### Installation

The `habitat_baselines` sub-package is NOT included upon installation by default. To install `habitat_baselines`, use the following command instead:
```bash
pip install -r requirements.txt
python setup.py develop --all
```
This will also install additional requirements for each sub-module in `habitat_baselines/`, which are specified in `requirements.txt` files located in the sub-module directory.


### Reinforcement Learning (RL)

**Proximal Policy Optimization (PPO)**

**paper**: [https://arxiv.org/abs/1707.06347](https://arxiv.org/abs/1707.06347)

**code**: majority of the PPO implementation is taken from 
[pytorch-a2c-ppo-acktr](https://github.com/ikostrikov/pytorch-a2c-ppo-acktr).
 
**dependencies**: pytorch 1.0, for installing refer to [pytorch.org](https://pytorch.org/)

For training on sample data please follow steps in the repository README. You should download the sample [test scene data](http://dl.fbaipublicfiles.com/habitat/habitat-test-scenes.zip), extract it under the main repo (`habitat/`, extraction will create a data folder at `habitat/data`) and run the below training command.

**train**:
```bash
python -u habitat_baselines/train_ppo.py \
    --use-gae \
    --sim-gpu-id 0 \
    --pth-gpu-id 0 \
    --lr 2.5e-4 \
    --clip-param 0.1 \
    --value-loss-coef 0.5 \
    --num-processes 4 \
    --num-steps 128 \
    --num-mini-batch 4 \
    --num-updates 100000 \
    --use-linear-lr-decay \
    --use-linear-clip-decay \
    --entropy-coef 0.01 \
    --log-file "train.log" \
    --log-interval 5 \
    --checkpoint-folder "data/checkpoints" \
    --checkpoint-interval 50 \
    --task-config "configs/tasks/pointnav.yaml" \


```

**test**:
```bash
python -u habitat_baselines/evaluate_ppo.py \
    --model-path "/path/to/checkpoint" \
    --sim-gpu-id 0 \
    --pth-gpu-id 0 \
    --num-processes 4 \
    --count-test-episodes 100 \
    --task-config "configs/tasks/pointnav.yaml" \


```

We also provide trained RGB, RGBD, Blind PPO models. 
To use them download pre-trained pytorch models from [link](https://dl.fbaipublicfiles.com/habitat/data/baselines/v1/habitat_baselines_v1.zip) and unzip and specify model path [here](agents/ppo_agents.py#L132).

Set argument `--task-config` to `tasks/pointnav_mp3d.yaml` for training on [MatterPort3D point goal navigation dataset](/README.md#task-datasets).

### Classic

**SLAM based**

- [Handcrafted agent baseline](slambased/README.md) adopted from the paper 
"Benchmarking Classic and Learned Navigation in Complex 3D Environments".
### Additional Utilities

**single-episode training**: 
Algorithms can be trained with a single-episode option. This option can be used as a sanity check since good algorithms should overfit one episode relatively fast. To enable this option, add `DATASET.NUM_EPISODE_SAMPLE 1` *at the end* of the training command, or include the single-episode yaml file in `--task-config` like this:
```
   --task-config "configs/tasks/pointnav.yaml,configs/datasets/single_episode.yaml"
```

**tensorboard and video generation support**

Enable tensorboard logging by adding `--tensorboard-dir logdir` when running `train_ppo.py` or `evaluate_ppo.py`

Enable video generation for `evaluate_ppo.py` using `--video-option`: specifying `tensorboard`(for displaying on tensorboard) or `disk` (for saving videos on disk), for example:
```
python -u habitat_baselines/evaluate_ppo.py   
...
--count-test-episodes 2 \
--video-option tensorboard \
--tensorboard-dir tb_eval \
--model-path data/checkpoints/ckpt.xx.pth
```
The above command should generate navigation episode recordings and display them on tensorboard like this:
<p align="center">
  <img src="../res/img/tensorboard_video_demo.gif"  height="500">
</p>
