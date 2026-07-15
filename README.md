# 两三天小项目：Whisper 本地语音转文字服务

**目标只有三个：上传一段 WAV → 得到识别文字 → 看到处理耗时。**

基于 whisper.cpp 自带的 C++ HTTP 服务端，增加少量 C++ 耗时统计，配一个只用 Python 标准库的客户端。使用已训练的多语言 tiny 模型，CPU 即可运行。

**本包已经用真实模型跑通。模型、固定版本源码、示例音频全部随包提供。工具安装完成后，编译和运行不需要再下载代码或权重。** 没有模拟识别模式。用户机器需要重新编译；已实测平台为 x86_64 Linux，Windows 请在 WSL2 的 Ubuntu 中执行以下命令。

## 1. 先用四步跑起来

解压 ZIP 后进入 `mini_whisper` 文件夹。若使用 Windows，以下命令应在 **WSL2 Ubuntu 终端**运行，不是 PowerShell；建议把项目放在 Linux 用户目录中。

### 第一步：安装基础工具

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 git ffmpeg
```

不需要 CUDA、显卡、PyTorch、Python 虚拟环境或 pip 包。包内模型已转换好；ffmpeg 只用于把自己的录音转为 WAV。

### 第二步：编译

在项目根目录执行：

```bash
bash build.sh
```

脚本先校验模型 SHA256，再编译 C++ 服务。首次编译可能需要几分钟。若出现内存不足导致编译被杀死，使用：

```bash
LAB_BUILD_JOBS=1 bash build.sh
```

### 第三步：启动服务

```bash
bash start.sh 4
```

末尾 `4` 是单次推理使用的计算线程数。看到监听 `127.0.0.1:8080` 的提示后，让这个终端保持运行。

### 第四步：在另一个终端提交示例音频

另开终端，同样进入 `mini_whisper`：

```bash
python3 client.py samples/jfk.wav --language en
```

正常会输出一段 JSON，包含 `text` 和毫秒单位的耗时。示例音频是英语，所以明确指定 `en`。本次真实识别文字为：

```text
And so my fellow Americans ask not what your country can do for you ask what you can do for your country.
```

标点、空白以及实际耗时不要求逐字或逐毫秒一致。验收看是否返回这段语音的实际内容。

停止服务：回到启动服务的终端，按 Ctrl+C。

## 2. 换成自己的中文语音

录一段 5–15 秒普通话，例如一段日常通知。把音频放到项目目录，再转换：

```bash
ffmpeg -i input.m4a -ar 16000 -ac 1 -c:a pcm_s16le samples/my_voice.wav
python3 client.py samples/my_voice.wav --language zh
```

`input.m4a` 改为你的实际文件名。客户端要求 16 kHz、单声道、16 位 PCM WAV，长度不超过 30 秒。模型是多语言 tiny，不是英文专用 `.en` 模型；tiny 的中文识别可能有错字，保留真实结果。包内已验证的是英语示例，中文效果由你的录音实测。

## 3. 两天怎么做

| 时间 | 要完成的事 | 验收 |
|---|---|---|
| 第一天上午 | 安装工具、编译、运行包内示例 | C++ 服务返回真实文字 |
| 第一天下午 | 换自己的录音，读懂 `client.py` | 能说明 HTTP 请求如何携带音频与语言参数 |
| 第二天上午 | 读 `my_changes.patch`，定位修改的 C++ 代码 | 能解释计时点和 `std::lock_guard` 的作用 |
| 第二天下午 | 按下节对比 1/4 线程，写半页结果 | 有自己机器的日志和真实耗时 |
| 第三天可用时 | 录一段演示，整理 README 与个人理解 | 展示“启动 → 提交录音 → 文本与耗时” |

这份安排假设你能使用 Linux 或已有 WSL2 环境。先完成这些验收，不增加新的功能。

## 4. 唯一一组性能实验：1 线程 vs 4 线程

保持同一个模型、同一段音频、同一台机器和相同解码设置。每组先预热一次，再顺序发 5 个请求。

先停掉现有服务，在终端 A：

```bash
bash start.sh 1
```

终端 B：

```bash
python3 client.py samples/jfk.wav --language en --warmup 1 --repeat 5 --out results/my_t1.json
```

终端 A 按 Ctrl+C，改为：

```bash
bash start.sh 4
```

终端 B：

```bash
python3 client.py samples/jfk.wav --language en --warmup 1 --repeat 5 --out results/my_t4.json
```

比较两个文件中的 `mean_client_ms`，并核对文字输出。`--out` 不会覆盖旧文件；重跑时换一个文件名。

本次制作时的实测如下，均排除 1 次预热，正式请求各 3 次：

| CPU 计算线程 | 成功转写 | 平均客户端耗时 |
|---|---:|---:|
| 1 | 3/3 | 1525.4 ms |
| 4 | 3/3 | 580.1 ms |

这些数字只描述本次机器与这一段音频的小样本结果。你的机器结果可能不同，不能直接当作你的项目测量，也不能据此宣称生产性能。原始结果见 `results/real_t1.json`、`results/real_t4.json`，环境见 `results/environment.json`。

## 5. 你需要读懂的代码很少

| 文件 | 作用 |
|---|---|
| `build.sh` | 检查模型，编译服务 |
| `start.sh` | 固定配置，启动 CPU 服务 |
| `client.py` | 校验 WAV，发送 multipart HTTP 请求，输出文字和耗时 |
| `my_changes.patch` | 展示我们对上游 C++ 服务增加的计时代码 |
| `vendor/whisper.cpp/examples/server/server.cpp` | C++ 服务源码；按补丁定位修改处即可 |
| `models/ggml-tiny.bin` | 已训练并转换好的真实模型 |

先读自己的小补丁和客户端，无须两天内读完 `vendor` 中的推理引擎。

耗时字段：

- `model_wait_ms`：进入业务 handler 后，等待模型互斥锁的时间。
- `processing_ms`：拿到锁后到构造结果前的时间，包含音频解析、特征处理和推理等，**不是纯神经网络计算时间**。
- `handler_ms`：以上两项之和，不包含进入 handler 之前的上传或 HTTP 调度等待。
- `client_ms`：Python 客户端发起请求到接收解析完 JSON 的时间。

上游服务用互斥锁保护共享模型，因此多个请求的模型处理会串行执行。`start.sh 4` 指一次推理使用 4 个计算线程，不代表 4 个请求同时推理。这个区别是你在项目介绍中应能解释的知识点。

## 6. 本项目做到什么程度

做到：真实语音识别、C++ HTTP 服务运行、小范围 C++ 修改、Python 客户端、一次可复现的线程参数实验。

暂不包含：训练模型、高并发服务改造、流式语音、动态 batch、GPU、KV Cache 改造或自研推理加速。这是两三天可完成的入门复现项目，不能覆盖整个招聘要求。

本人完成上述步骤并理解代码后，项目可如实介绍为：

> 复现基于 whisper.cpp 的本地语音转写服务，使用 Python 客户端提交 WAV 音频；为 C++ 接口增加模型锁等待及处理耗时统计，并对比 CPU 推理线程配置对请求耗时的影响。

上游模型、推理引擎、HTTP 框架均为现成组件；本包小补丁与客户端由 AI 辅助制作。面试前至少能解释一次请求的流程、为什么要锁、计算线程与并发请求的区别，以及自己的真实测量结果。

## 7. 常见问题

- **找不到 cmake/g++**：重新检查第一步工具安装。
- **端口 8080 被占用**：先停止另一个正在运行的服务，再启动当前服务。
- **Connection refused**：确认启动终端仍在运行，并已显示监听成功。
- **音频格式错误**：按第 2 节先用 ffmpeg 转码，不能只改扩展名。
- **第一次比后续慢**：首次调用可能有额外初始化；性能对照按文档预热。
- **illegal instruction**：默认构建针对现代 x86 CPU；旧 CPU 需调整 ggml 指令集选项，本包未验证所有 CPU。
- **中文有错字**：保留原始录音、参考文字与识别结果。先完成项目流程，tiny 的小模型能力不是代码正确性的保证。

运行地址固定为本机 `127.0.0.1`，用于个人实验；无需开放公网端口。

## 8. 来源和复现记录

- [Whisper 论文](https://arxiv.org/abs/2212.04356)。
- [OpenAI Whisper](https://github.com/openai/whisper)：原始模型与转换所需 tokenizer/mel assets，代码和权重 MIT 许可。
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)：固定 `v1.7.6`，commit `a8d002cfd879315632a579e73f0148d06959de36`，MIT。
- 原始权重 SHA256 已对照官方 URL 中的校验值验证；转换后的权重校验值、转换来源记录在 `models/model.json`。
- 示例 `samples/jfk.wav` 来自该版本 whisper.cpp 的 samples；上游版权/许可文件保留在 `vendor/whisper.cpp`。
- 本包不包含编译产物。工具安装后，源码与模型足够本地编译运行，无需在线拉取额外模型或代码。
- 包内结果为真实模型运行，无 mock；已在 Linux x86_64 / GCC 13.3 / Python 3.12 / CPU 上成功编译与验证。Windows 原生和 macOS 未实测。
