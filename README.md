# \# Mini-Whisper-Bench: Local C++ Speech Recognition \& Profiling Service

# 

# 本项目基于 `whisper.cpp` (v1.7.6) 构建了轻量级的本地语音转写 (ASR) HTTP 服务。项目专注于 C++ 服务端的并发安全与性能观测，通过引入互斥锁保护共享模型上下文，并实现了微秒级的全链路耗时打点。配套提供基于纯 Python 标准库的零依赖客户端，完成了 CPU 多线程推理的性能基准测试\[cite: 4]。

# 

# \## 核心架构与特性

# 

# \### 1. 线程安全与并发控制

# \* \*\*模型资源锁\*\*：针对上游服务端共享 Whisper 模型实例的特性，采用 `std::lock\\\\\\\_guard` 互斥锁机制进行保护\[cite: 4]。在高并发请求涌入时，确保多个请求的模型处理阶段严格串行执行\[cite: 4]，避免发生竞态条件与内存越界崩溃。

# 

# \### 2. 精细化性能观测 (Profiling)

# 在 C++ 服务端核心业务流中注入高精度计时器，暴露出以下关键延迟指标以供性能瓶颈分析\[cite: 4]：

# \* `model\\\\\\\_wait\\\\\\\_ms`：进入业务 handler 后，排队等待获取模型互斥锁的阻塞耗时\[cite: 4]。

# \* `processing\\\\\\\_ms`：拿到锁后直到构造结果前的时间，涵盖音频解析、特征提取与模型推理解码（非纯神经网络计算时间）\[cite: 4]。

# \* `handler\\\\\\\_ms`：服务端业务逻辑总耗时（即 `model\\\\\\\_wait\\\\\\\_ms` 与 `processing\\\\\\\_ms` 之和）\[cite: 4]。

# \* `client\\\\\\\_ms`：Python 客户端从发起 HTTP 请求到接收并解析完 JSON 的端到端总耗时\[cite: 4]。

# 

# \### 3. 零外部依赖压测套件

# \* 摒弃复杂的第三方依赖，完全基于 Python 3 标准库构建 HTTP multipart 上传客户端\[cite: 4]。支持自定义并发度、预热次数与执行轮次，直接输出格式化的性能基准测试 JSON 报告\[cite: 4]。

# 

# \## 性能基准测试 (Benchmarks)

# 

# 基于已训练的 OpenAI Whisper Tiny 多语言模型 (CPU 后端)\[cite: 4]，在相同硬件环境与解码设置下，针对标准英文音频进行控制变量压测（均排除 1 次预热，记录 3 次正式请求的平均值）\[cite: 4]：

# 

# | CPU 计算线程 (Threads) | 成功转写 | 平均客户端端到端耗时 (`client\\\\\\\_ms`) | 加速比 |

# | :---: | :---: | :---: | :---: |

# | \*\*1 Thread\*\* | 3/3\[cite: 4] | 1525.4 ms\[cite: 4] | 1.0x (Baseline) |

# | \*\*4 Threads\*\* | 3/3\[cite: 4] | 580.1 ms\[cite: 4] | \*\*\~2.63x\*\* |

# 

# > \*\*工程结论\*\*：单次推理分配 4 个计算线程（`start.sh 4`）相较于单线程，大幅缩减了矩阵乘法耗时\[cite: 4]。但需要明确区分计算线程与并发请求：由于互斥锁的存在，即便分配了多线程，模型层面的处理依然是串行的，计算线程增加不代表支持 4 个请求同时进行并发推理\[cite: 4]。

# 

# \## 快速构建与运行

# 

# 本项目使用 CPU 即可运行，不依赖 CUDA、显卡、PyTorch 或任何 pip 包\[cite: 4]。已实测平台为 x86\_64 Linux (或 WSL2 Ubuntu)\[cite: 4]。

# 

# \### 环境初始化与编译

# ```bash

# \# 安装基础编译工具与 ffmpeg (仅用于用户录音转码)

# sudo apt update\[cite: 4]

# sudo apt install -y build-essential cmake python3 git ffmpeg\[cite: 4]

# 

# \# 校验模型并编译 C++ 服务

# bash build.sh\[cite: 4]

