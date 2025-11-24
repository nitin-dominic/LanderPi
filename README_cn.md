# LanderPi

[English](https://github.com/Hiwonder/LanderPi/blob/main/README.md) | 中文

<p align="center">
  <img src="./sources/images/landerpi.png" alt="LanderPi Logo" width=600px "/>
</p>


## LanderPi：一个能听懂人话、自己动脑的机器人学习和开发平台

我常常在想，能不能让机器人像人一样，听到「把红色积木拿过来」就能自主找到，精准规划动作？这就是LanderPi的起点——一个真正能听懂指令、自己思考怎么执行的机器人平台。这也是一个让热爱学习AI的学生、开发者，工程师们都能轻松学习先进的AI机器人技术，并能创作出更多AI项目的机器人开发平台。

<p align="center">
  <img src="./sources/images/1.png" alt="LanderPi 概览" width="600"/>
</p>

## 多模态AI大模型+ROS2

LanderPi基于 ROS2 开发，部署了多模态AI大模型，你只需要用自然语言发出指令，它就能自己"听懂指令-解析环境-规划路径-精准操作"。不管是「追踪牛奶旁白的物品」还是「分拣数量最多的色块」，它都能理解你的意图并自主完成。

<p align="center">
  <img src="./sources/images/2.png" alt="多模态AI + ROS2" width="600"/>
</p>

### 强大的硬件配置

LanderPi采用树莓派5与STM32构建出控制系统，并搭载了3D深度相机、6DOF机械臂、TOF激光雷达、AI语音交互盒，为机器人建立了完整的感知能力。你还可以根据应用场景，选择阿克曼底盘、麦克纳姆轮或坦克履带三种底盘配置中的任何一种。

<p align="center">
  <img src="./sources/images/3.png" alt="硬件配置 1" width="600"/>
</p>

<p align="center">
  <img src="./sources/images/4.png" alt="硬件配置 2" width="600"/>
</p>

### 高精度建图与导航

我们为LanderPi配备了TOF激光雷达，能够以厘米级精度扫描和建图环境。想让它导航到特定位置、执行多点路线或自主巡逻？不成问题！当突然出现障碍物时，LanderPi会实时感知、平滑躲避，并自动重新规划路线。即使在复杂环境中，LanderPi也能自信地自主运动。

<p align="center">
  <img src="./sources/images/5.png" alt="建图与导航" width="600"/>
</p>

### 3D视觉精准抓取

LanderPi配备的高精度3D相机能够检测物体的颜色、位置和距离。这个相机安装在机械臂末端，配合我们的逆运动学解决方案，实现了真正的手眼协调。无论物体摆放多么凌乱，LanderPi都能精准识别目标并拾起。

<p align="center">
  <img src="./sources/images/6.png" alt="3D视觉抓取" width="600"/>
</p>

### 用AI和你的机器人对话

LanderPi搭载多模态AI大模型，不仅能听到你的声音，更能理解当前的场景。不管你说的是「把红色的东西拿过来」这种简单指令，还是「找出所有蓝色物体中最大的那个」这种复杂条件，它都能转换成自己的理解，然后自己想办法执行。

<p align="center">
  <img src="./sources/images/7.png" alt="AI语音交互" width="600"/>
</p>

### YOLOv11深度学习算法

基于YOLOv11的深度学习算法为LanderPi提供了强大的物体识别与分类能力。结合3D视觉系统，让机器人不仅能"看到"物体，更能"理解"它们，实现真正的智能视觉决策。

<p align="center">
  <img src="./sources/images/8.png" alt="YOLOv11视觉识别" width="600"/>
</p>

## 完全开源，代码随便拿，随便改！

我们的所有代码完全开放：从机器人控制、AI大模型交互、3D视觉识别和机械臂控制，全部放在GitHub上。你可以直接使用现有模块，也可以基于我们的框架开发新功能。

如果你也想折腾一个能听懂人话、自己动脑的机器人，欢迎来我们的代码库看看。这里有完整的使用教程和开发文档，让我们一起把机器人变得更酷。

<p align="center">
  <img src="./sources/images/9.png" alt="开源社区" width="600"/>
</p>

## 官方资源

### Hiwonder官方
- **官方网站**: [https://www.hiwonder.com/](https://www.hiwonder.com/)
- **产品页面**: [https://www.hiwonder.com/products/landerpi](https://www.hiwonder.com/products/landerpi)
- **官方文档**: [https://docs.hiwonder.com/projects/LanderPi/en/latest/](https://docs.hiwonder.com/projects/LanderPi/en/latest/)
- **技术支持**: support@hiwonder.com

## 项目结构

```
landerpi/
├── src/                    # 源代码模块
├── command                 # 命令参考和工具
└── sources/                # 资源和文档
    └── images/             # 产品图片和媒体
```

## 版本信息
- **当前版本**: LanderPi v1.0.0
- **支持平台**: 树莓派5

### 相关技术
- [ROS2](https://ros.org/) - 机器人操作系统2
- [MoveIt](https://moveit.ros.org/) - 运动规划框架
- [OpenCV](https://opencv.org/) - 计算机视觉库
- [YOLOv11](https://github.com/ultralytics/yolov11) - 目标检测框架

---

**注**: 所有程序已预装在LanderPi机器人系统中，可直接运行。详细使用教程请参考[官方文档](https://docs.hiwonder.com/projects/LanderPi/en/latest/)。
