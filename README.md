# Mini Whisper：本地 CPU 语音转写服务

这是项目的**基础计时版**：基于 [whisper.cpp](https://github.com/ggml-org/whisper.cpp) 的 C++ HTTP 服务，在 CPU 上运行 Whisper Tiny 多语言模型，提供 WAV 音频上传、文字转写和请求耗时统计。仓库还包含一个仅使用 Python 标准库的客户端，以及可复现的 1/4 计算线程对照实验。

本版本的改动集中在**接入和观测**：复用上游推理引擎与 HTTP 服务，为 JSON 响应增加模型锁等待时间、处理时间和 handler 总耗时。模型和上游框架均非本项目从零实现。

## 功能与技术栈

|部分|实现|
|-|-|
|语音转写|Whisper Tiny 多语言权重；whisper.cpp / ggml CPU 推理|
|服务端|C++、cpp-httplib、nlohmann/json；`POST /inference` 接收 multipart 音频|
|并发保护|共享 Whisper context 由 `std::mutex` 保护；此版本的模型处理按请求串行执行|
|客户端|Python 3 标准库：WAV 校验、HTTP 上传、结果与耗时记录|
|构建环境|Linux x86\_64、GCC、CMake、Bash；Windows 可在 WSL2 Ubuntu 中运行|

`bash start.sh 4` 中的 `4` 是**一次推理使用的 CPU 计算线程数**，不是同时运行 4 个模型请求。

## 快速运行

仓库根目录应包含 `models/ggml-tiny.bin`、`vendor/whisper.cpp` 和 `samples/jfk.wav`。模型文件为已转换的真实权重；`build.sh` 会检查其 SHA256。源码和权重齐备后，编译无需再下载依赖代码或模型。

在 Ubuntu 或 WSL2 Ubuntu 中安装工具：

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 ffmpeg
```

在仓库根目录编译并启动：

```bash
bash build.sh
bash start.sh 4
```

若编译时内存不足，可以用 `LAB\\\\\\\_BUILD\\\\\\\_JOBS=1 bash build.sh` 减少并行编译任务。服务默认只监听本机 `127.0.0.1:8080`；让启动终端保持运行。

另开一个终端，在仓库根目录提交示例音频：

```bash
python3 client.py samples/jfk.wav --language en
```

示例音频的转写内容如下。具体标点和空白可能因解码结果有所不同：

```text
And so my fellow Americans ask not what your country can do for you ask what you can do for your country.
```

客户端输出包含 `text`、`model\\\\\\\_wait\\\\\\\_ms`、`processing\\\\\\\_ms`、`handler\\\\\\\_ms` 和 `client\\\\\\\_ms`。下方根据一条历史实测记录整理，省略了转写文本末尾的换行；时间数值只对应当时的测试环境：

```json
{
  "text": " And so my fellow Americans ask not what your country can do for you ask what you can do for your country.",
  "model\\\\\\\_wait\\\\\\\_ms": 0.001,
  "processing\\\\\\\_ms": 484.138,
  "handler\\\\\\\_ms": 484.139,
  "client\\\\\\\_ms": 486.013
}
```

也可以直接调用 HTTP 接口：

```bash
curl -F 'file=@samples/jfk.wav' -F 'language=en' -F 'response\\\\\\\_format=json' http://127.0.0.1:8080/inference
```

停止服务时，在启动终端按 `Ctrl+C`。

## 转写自己的录音

客户端接受 **16 kHz、单声道、16 位 PCM WAV**，时长不超过 30 秒。其他音频格式可以先用 FFmpeg 转换：

```bash
ffmpeg -i input.m4a -ar 16000 -ac 1 -c:a pcm\\\\\\\_s16le samples/my\\\\\\\_voice.wav
python3 client.py samples/my\\\\\\\_voice.wav --language zh
```

`input.m4a` 请换成自己的文件。模型支持多语言，但 Tiny 规模的中文转写可能出现错字；仓库内提供的固定示例与实测记录使用英语音频。

## 耗时字段与请求流程

一次请求依次经过 HTTP 音频上传、等待共享模型锁、WAV 解析、Whisper 推理和结果构造。本历史版本在解析音频前就取得模型锁。JSON 响应中的字段按下表理解：

|字段|含义|
|-|-|
|`model\\\\\\\_wait\\\\\\\_ms`|进入业务 handler 后等待模型互斥锁的时间|
|`processing\\\\\\\_ms`|取得模型锁后到结果构造前的时间，包含音频解析和推理，并非纯神经网络计算时间|
|`handler\\\\\\\_ms`|业务 handler 内的总时间；不包含此前的 HTTP 上传与调度等待|
|`client\\\\\\\_ms`|Python 客户端从发起请求到收到并解析响应的时间|

多个请求共用一个模型 context，因此需要互斥锁保护。本版本记录等待与处理耗时，未实现独立的业务任务线程池或多请求并行推理。

## 计算线程对照实验

保持同一模型、同一音频、同一机器和相同解码参数。下面的两组命令各预热 1 次，再记录 3 次顺序请求；每组运行前都要先停止上一个服务。

终端 A 先启动 1 个计算线程，终端 B 发请求：

```bash
# 终端 A
bash start.sh 1
```

```bash
# 终端 B
python3 client.py samples/jfk.wav --language en --warmup 1 --repeat 3 --out results/my\\\\\\\_t1.json
```

停止终端 A 的服务，再改用 4 个计算线程：

```bash
# 终端 A
bash start.sh 4
```

```bash
# 终端 B
python3 client.py samples/jfk.wav --language en --warmup 1 --repeat 3 --out results/my\\\\\\\_t4.json
```

历史版本在一台 Linux x86\_64 / GCC 13.3 / Python 3.12 的 CPU 环境下得到以下结果：

|单次推理计算线程数|成功转写|平均客户端耗时|
|-:|-:|-:|
|1|3/3|1525.4 ms|
|4|3/3|580.1 ms|

每组仅 3 次正式请求。这是固定样本上的小规模对照，不能作为模型吞吐、通用加速比或线上容量结论。原始记录见 [`results/real\\\\\\\_t1.json`](results/real_t1.json)、[`results/real\\\\\\\_t4.json`](results/real_t4.json)，运行环境见 [`results/environment.json`](results/environment.json)。`--out` 不会覆盖已有文件，重复实验时请更换输出文件名。

## 仓库结构

|路径|内容|
|-|-|
|`build.sh`、`start.sh`|模型校验、编译和本地服务启动|
|`client.py`|WAV 校验、multipart 上传、顺序请求和耗时记录|
|`my\\\\\\\_changes.patch`|相对固定上游版本的 C++ 计时改动|
|`vendor/whisper.cpp/`|固定版本的上游源码，服务入口位于 `examples/server/server.cpp`|
|`models/`|转换后的 Tiny 权重、校验与来源记录|
|`samples/jfk.wav`|英语语音示例|
|`results/`|编译、转换和 CPU 线程实验记录|

本版本用于本地 CPU 语音转写与耗时观测。流式识别、动态批处理、GPU 推理和自研模型优化均不在此版本的实现范围内。

## 上游来源与许可

* [Whisper 论文](https://arxiv.org/abs/2212.04356)；[OpenAI Whisper](https://github.com/openai/whisper) 提供预训练模型与转换所需资源，模型来源和 SHA256 见 [`models/model.json`](models/model.json)。
* [whisper.cpp](https://github.com/ggml-org/whisper.cpp) 固定为 `v1.7.6`，commit `a8d002cfd879315632a579e73f0148d06959de36`；上游许可文件保留在 [`vendor/whisper.cpp/LICENSE`](vendor/whisper.cpp/LICENSE)。
* 模型相关许可见 [`models/OPENAI\\\\\\\_WHISPER\\\\\\\_LICENSE`](models/OPENAI_WHISPER_LICENSE)。`samples/jfk.wav` 来自该版本 whisper.cpp 的示例音频。

服务端的少量计时改动与 Python 客户端由 AI 辅助编写，并通过真实模型运行验证。这里的实验数据仅来自随仓库记录的测试环境。

