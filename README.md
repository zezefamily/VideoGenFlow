# VideoGenFlow

VideoGenFlow 是一个面向短视频创作的对话式 Creative Agent。用户可以提交短视频分享链接、一个话题，或现成口播文案，Agent 会在同一会话中完成参考视频分析、口播脚本、分镜、分镜图、配音、字幕打轴和最终成片，并在每个阶段主动确认下一步。

## SHOWCASE

### 一只马蜂，干掉三吨野牛

- 时长：65.568 秒
- 模式：Seedance 动态镜头与静态分镜混合成片
- [下载仓库内高清成片](./demo/videos/一只马蜂-干掉三吨野牛.mp4)

https://github.com/user-attachments/assets/0a703bec-0625-47a9-b377-9a14a3ab9707

### 章鱼之死：愤怒如何绞碎你

- 时长：79.296 秒
- 模式：Seedance 动态镜头与静态分镜混合成片
- [下载仓库内高清成片](./demo/videos/章鱼之死-愤怒如何绞碎你.mp4)

https://github.com/user-attachments/assets/5bf22571-0311-4b0b-8bd2-798d3a14035a

> GitHub 会将上方 Attachment 地址渲染为视频播放器；仓库内同时保留高清 MP4，便于下载和离线播放。

## 主要能力

- 对话式创作：支持闲聊，并引导用户回到短视频创作主线。
- 三种创作入口：短视频链接分析、从话题开始、从口播文案继续。
- 参考视频分析：通过字幕、视频下载和 Whisper ASR 提取原始口播，分析钩子、结构和受众痛点。
- 版本化产物：脚本和分镜支持多版本、局部修改、激活与回退。
- 分镜图生成：使用火山方舟 Seedream，并使用前一镜作为参考维持视觉连续性。
- 双 TTS 供应商：支持 DubbingX 和豆包语音，可在设置中选择供应商。
- 字幕时间轴：使用火山引擎 ATA 获取逐句、逐词时间戳。
- 自动成片：使用 ffmpeg 拼接分镜、配音、黄色描边字幕和背景音乐。
- 可选视频成片：使用 Seedance 2.0 mini 将选中的分镜图生成 480p 无声视频，再与静态镜头混合合成。
- 上下文素材规划：重新合成前检查当前及历史产物，按兼容性决定复用、确认或重新生成。
- 流式交互：通过 SSE 展示 Agent 回复、节点进度和后台任务状态，切换会话后可恢复。
- 开发/生产双模式：SQLite/PostgreSQL、本地存储/S3、进程内任务/Redis + Arq。

## 技术栈

- 前端：Next.js 14、React 18、TypeScript、Tailwind CSS、TanStack Query
- Agent 编排：LangGraph（状态图、条件路由、Checkpoint、流式执行）
- 模型调用：LangChain（模型适配、Prompt 模板、消息对象、输出解析）
- 后端：FastAPI、SQLAlchemy 2、Pydantic、SSE
- 模型服务：DeepSeek、火山方舟 Seedream、豆包语音、DubbingX、火山 ATA
- 媒体处理：yt-dlp、faster-whisper、ffmpeg、Pillow
- 数据：SQLite（开发默认）、PostgreSQL（可选）

## LangGraph Agent 架构

LangGraph 是项目中一轮对话的核心工作流引擎，不只是模型调用依赖。它负责加载会话状态、识别意图、选择业务节点、传递产物上下文，并将执行过程流式推送到前端。

```text
START
  ↓
load_context          从业务数据库恢复历史、脚本、分镜、音轨和成片
  ↓
classify_intent       确定性规则 + LLM 意图识别
  ↓
  ├─ analyze_video
  ├─ generate_script / revise_script
  ├─ generate_storyboard / revise_storyboard
  ├─ generate_images
  ├─ generate_tts
  ├─ render_video
  └─ respond
       ↓
      END
```

相关代码：

- `apps/api/app/graph/state.py`：定义图节点共享的 `ChatState`。
- `apps/api/app/graph/builder.py`：注册节点、条件边和完整执行图。
- `apps/api/app/graph/nodes/`：意图分类及各阶段业务节点。
- `apps/api/app/graph/tracking.py`：统一记录节点开始、完成和错误事件。
- `apps/api/app/services/run_executor.py`：通过 `graph.astream()` 执行图并向前端发送 SSE。
- `apps/api/app/main.py`：初始化 SQLite 或 PostgreSQL Checkpointer。

LangGraph 状态用于单轮节点协作和执行检查点；脚本、分镜、图片、音轨和成片仍以业务数据库为真源，每轮由 `load_context` 重新加载。这能避免仅依赖模型记忆而造成素材版本判断错误。

## 项目结构

```text
VideoGenFlow/
├── apps/
│   ├── api/                  # FastAPI、LangGraph、领域服务与后台任务
│   │   └── app/
│   │       ├── api/          # HTTP/SSE 路由
│   │       ├── graph/        # Agent 状态、意图分类与工作流节点
│   │       ├── models/       # SQLAlchemy 模型
│   │       ├── repositories/ # 数据访问层
│   │       ├── schemas/      # Pydantic API 契约
│   │       └── services/     # 分析、出图、TTS、ATA、成片等服务
│   └── web/                  # Next.js 对话客户端
├── bg_music/                 # 成片背景音乐库
├── demo/videos/              # 随仓库提供的默认成片演示
├── data/                     # SQLite、检查点、图片、音频和视频
├── scripts/mocks/            # 交互调试 Mock 数据
├── .env.example              # 环境变量模板
├── requirements.txt          # Python 依赖
└── ChangeLog.md              # 项目变更记录
```

## 本地运行

### 1. 环境要求

- Python 3.11+
- Node.js 18+
- npm
- ffmpeg 和 ffprobe
- macOS 使用链接分析时建议安装 Chrome，或在环境变量中关闭浏览器 Cookie。

macOS 可通过 Homebrew 安装媒体工具：

```bash
brew install ffmpeg
```

### 2. 安装后端依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

至少配置文本模型：

```dotenv
DEEPSEEK_API_KEY=your-key
DEEPSEEK_MODEL=deepseek-v4-flash
```

需要出图时配置：

```dotenv
ARK_API_KEY=your-key
ARK_IMAGE_MODEL=doubao-seedream-5-0-260128
ARK_VIDEO_MODEL=doubao-seedance-2-0-mini-260615
ARK_VIDEO_RESOLUTION=480p
ARK_VIDEO_COST_PER_SECOND=0.25
```

使用豆包语音时配置：

```dotenv
TTS_PROVIDER=volcengine
VOLC_TTS_APPID=your-app-id
VOLC_TTS_ACCESS_TOKEN=your-access-token
VOLC_TTS_CLUSTER=volcano_tts
VOLC_TTS_VOICE_TYPE=zh_female_shuangkuaisisi_emo_v2_mars_bigtts
```

豆包默认参数：爽快思思、`coldness`、音调 -1、默认音量。官方体验页“语速 20”对应 HTTP API `speed_ratio=1.2`。

字幕打轴还需要配置 `VOLC_ATA_*` 和可公开访问的临时 TOS 存储。完整配置见 [.env.example](./.env.example)。不要提交真实 `.env` 或任何访问密钥。

### 4. 启动后端

```bash
cd apps/api
../../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查与 API 文档：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/docs
```

### 5. 启动前端

```bash
cd apps/web
npm install
npm run dev
```

访问 `http://localhost:3001/`。开发默认账号为 `dev@videogenflow.local / devpassword`；生产环境必须修改 `JWT_SECRET` 和默认密码。

## 创作流程

```text
链接 / 话题 / 口播文案
          ↓
理解意图与加载会话上下文
          ↓
参考分析 → 脚本 → 分镜 → 分镜图 → 配音/字幕 → 成片
          ↑       每个阶段由用户确认、修改或继续       ↓
          └────────── 版本与依赖状态恢复 ──────────┘
```

制作类指令采用确定性路由优先：

- `语音部分换成豆包再试试`：重新生成豆包配音，不修改脚本。
- `重新语音合成`：使用当前激活脚本重新生成音轨。
- `重新合成视频`：先检查必要素材，再直接合成或提示缺失项。
- `复用旧画面直接合成`：允许使用中等匹配度的历史分镜，并按新字幕时间轴重新对齐。

## 音画同步策略

配音字幕时间轴是成片的唯一主时钟。系统使用 ATA 的真实字幕时间，将分镜旁白映射到当前口播文本：

- 当前分镜和脚本一致时直接对齐。
- 历史分镜与新脚本高度相似时自动复用。
- 中等相似时需要用户明确同意复用旧画面。
- 匹配度低于 45% 时拒绝强行复用，建议重新生成分镜。
- 被新脚本删除的旧镜头会被压缩跳过，避免后续画面累计偏移。

调整 TTS 语速不能修复版本错位；脚本、分镜、图片和音轨的依赖关系必须先正确。

## 视频成片模式

素材齐备后可选择：

- 图片成片：保持现有静态分镜合成，不产生视频生成费用。
- 视频成片：使用分镜图作为首帧、现有 `video_prompt` 作为提示词，通过 Seedance 2.0 mini 生成 480p 无声视频。

视频成片支持三种策略：智能生成、全部生成、自定义镜头。智能模式固定选择首镜和尾镜，并根据动作、运镜和镜头间隔选择约三分之一镜头。界面会按各分镜生成时长之和 × `ARK_VIDEO_COST_PER_SECOND` 展示预算，只有用户确认后才提交付费任务。已经成功且提示词未变化的镜头视频会复用；失败镜头在最终合成时自动回退为图片。

## 背景音乐与字幕

- 将 MP3、WAV、M4A、AAC、FLAC 或 OGG 放入 `bg_music/`。
- 合成时选取按文件名排序后的第一首音乐，并循环至口播结束。
- 背景音乐以低音量与口播混合。
- 字幕使用亮黄色、粗黑描边样式，并清理容易产生异常字框的停顿标点。

## 数据与产物

开发模式默认写入：

```text
data/app.sqlite          # 业务数据
data/checkpoints.sqlite  # LangGraph 检查点
data/images/             # 分镜图片
data/audio/              # 配音
data/videos/             # 成片
```

脚本、分镜、图片、音轨和成片通过版本 ID 建立依赖关系。调试时若清理错误版本，必须先备份数据库，并同步处理引用该版本的音轨、成片和消息卡片。

## 生产配置

- `DATABASE_URL`：切换 PostgreSQL
- `STORAGE_BACKEND=s3` 与 `S3_*`：切换 S3 兼容对象存储
- `TASK_RUNNER=arq` 与 `REDIS_URL`：切换 Redis + Arq 后台任务
- `SENTRY_DSN`：错误追踪
- `RATE_LIMIT`：接口限流
- `NEXT_PUBLIC_API_URL`：前端后端地址

Arq Worker：

```bash
cd apps/api
../../.venv/bin/arq app.worker.WorkerSettings
```

上线前应检查 Worker 已注册所需任务类型，并建立正式的数据库迁移、对象存储生命周期、任务重试和凭证轮换流程。

## 常用验证

```bash
.venv/bin/python -m compileall -q apps/api/app
cd apps/web && npm run build
curl http://127.0.0.1:8000/api/health
curl -I http://127.0.0.1:3001/
```

## 调试页面

- `/debug/mock`：会话交互 Mock 调试
- `/debug/tts`：TTS 参数与音频调试

调试页面不建议暴露在生产环境。

## 当前限制

- 历史分镜与新脚本差异较大时无法保证语义一致，必须重新生成分镜或人工确认复用。
- 短视频链接解析受平台反爬、Cookie 和网络环境影响。
- 进程内后台任务在服务重启时会中断；生产环境应使用持久任务队列。
- 当前前端仅开放供应商选择，豆包音色和参数使用固定默认值。
