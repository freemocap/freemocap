# FreeMoCap 学习 Fork

这是 `mybir` 基于 [FreeMoCap](https://github.com/freemocap/freemocap) 的 fork。

## 用途
- 学习开源动作捕捉系统：多摄像头采集 → 2D 姿态识别 → 三角测量 → 3D 骨骼重建
- 在其基础上构建篮球动作分析能力，作为嵌入式工程师转型求职的作品集
- 向 FreeMoCap 上游提交修复与改进（通过 Pull Request）

## 协议
FreeMoCap 使用 AGPL-3.0。本 fork 同样以 AGPL-3.0 开源，全部源码公开。

## 与上游保持同步
定期执行以下命令将官方更新合入本地：

    git fetch upstream
    git merge upstream/main

`main` 分支保持为上游的干净镜像；所有学习与改动都在独立分支上进行，再向上游提 PR。
