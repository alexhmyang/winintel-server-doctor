# ⚡ winintel AI 服务器一键安装与验收

**给客户装得上，给工程师查得清，给 AI Agent 看得懂。**

🌐 [官网 winintel.com](https://winintel.com) · 📺 [Bilibili](https://space.bilibili.com/429959998) · 🎬 [YouTube](https://www.youtube.com/@winintelcom) · 🌍 [English](README.md)

| 一键完成 | 内容 |
|---|---|
| 🟢 驱动安装 | Ubuntu 仓库中最新的 V100 兼容 R580-server 专有驱动补丁 |
| 🧰 CUDA | 12.8 / 11.6 / 13.0 按需安装、并存、切换 |
| 🔥 GPU 压测 | gpu-burn 校验计算结果，逐卡判断，检查 ECC，记录功耗/利用率 |
| ⚙️ CPU、内存 | stress-ng 校验 + sysbench 测速 |
| 💾 硬盘 | fio CRC32C 校验、顺序读写、4K 随机读取 IOPS |
| 🔌 PCIe | 速率、通道宽度、CPU↔GPU 传输速度、多卡 P2P 带宽与延迟 |
| 📊 验收报告 | HTML 给客户看，JSON 给 AI Agent，Markdown 方便存档 |

## 三步开始

下载并解压 [发行包](https://github.com/alexhmyang/winintel-server-doctor/releases/tag/v0.1.0)，进入目录后运行：

```bash
sudo bash install.sh
```

在维护窗口重启，再确认：

```bash
nvidia-smi
winintel-doctor inventory
```

一键验收：

```bash
sudo winintel-doctor test \
  --profile /opt/winintel-server-doctor/profiles/v100-sxm2-8gpu.json \
  --disk-path /var/tmp --seconds 60
```

打开生成的 `reports/时间/report.html`，即可查看验收结果。报告不会自动上传。

安装大约 10–30 分钟，受网络、缓存和内核编译影响；默认完整验收约 8–15 分钟。压测会占用服务器资源，请安排维护窗口。

## V100 要选对版本

**V100 推荐 R580 专有驱动 + CUDA 12.8。** 默认安装不会追到已经不支持 V100 的更新驱动分支。“最新”指 Ubuntu 仓库已发布并被镜像同步的 R580-server 最新补丁，不等于 NVIDIA 上游绝对最新补丁。

- **CUDA 12.8：** V100 推荐版本，支持 Ubuntu 22.04、24.04。
- **CUDA 11.6：** 兼容 V100，本项目在 Ubuntu 22.04 配套 GCC 10；24.04 建议用容器。
- **CUDA 13.0：** 已删除 V100 的编译和库支持。可以为其他新显卡安装工具包，不能用于 V100 运算。

`nvidia-smi` 显示 CUDA 13，只表示驱动 API 能力，不能据此认定 V100 可以用 CUDA 13 工具包。

```bash
# V100 两套可用工具包
sudo bash install.sh --cuda 12.8,11.6

# Ubuntu 22.04 安装三套，明确接受 CUDA 13 仅供其他兼容显卡使用
sudo bash install.sh --cuda all --allow-unsupported-cuda13

# 当前终端切换环境
source /opt/winintel-server-doctor/cuda-env.sh 12.8
```

安装使用清华 Ubuntu 镜像和 NVIDIA 中国下载地址；GPU 测试源码随包携带，不需要现场从 GitHub 下载。不会自动重启、修改显卡功率或清除现有模型。

## 什么才算达标

默认 8 卡 V100 SXM2 配置检查：8 张 V100、32GB 级显存、300W 功率上限、PCIe Gen3 ×16、单向传输至少 10,000 MB/s。PCIe 版 V100 常见功率上限为 250W，应改用实际板卡要求。

CPU 核心数、内存容量/插条数/配置速率、硬盘速度应按客户订单填写 JSON 配置。不能拿一个固定跑分判断所有服务器，也不能把“没测到”写成合格。

**PASS：符合门槛；FAIL：不符合；UNKNOWN：未设门槛、未测试或数据不足。** 整体未完成会返回 `3`，发现失败返回 `2`。

内存条数量不等于内存通道数。需要按主板说明书提供 DIMM 插槽到 CPU/通道的映射，才能判断通道配置；映射方法见 [测试说明](docs/TESTING.md)。

磁盘测试只写独立临时文件，不接收裸盘设备。PCIe 链路可能在空闲时降速，报告会同时保留传输测试结果和采样值，便于核对。

## AI Agent 使用

先读 [AGENTS.md](AGENTS.md)，执行 `--dry-run` 获取计划。实际运行结束后读取 stdout 最后一行 JSON，再读取 `report.json`，根据退出码继续处理。不要把安装后尚未重启、未运行验收的服务器标为交付合格。

首版实际验证范围见 [VALIDATION.md](docs/VALIDATION.md)。文档中的配置数值是示例门槛，不是伪造的硬件实测成绩。

⭐ 欢迎 Star、分享客户验收配置、提交兼容性反馈，让更多 V100 服务器继续发挥价值。

**数萌AI服务器 (winintel)** · [winintel.com](https://winintel.com) · service@winintel.com
