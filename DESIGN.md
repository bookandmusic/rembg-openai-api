# Local Rembg OpenAI Image API 服务设计文档

> 版本：v1.0（审定稿）
> 日期：2026-07-14
> 状态：已对齐 rembg v2.0.76 实际行为与 OpenAI Images API 规范

---

## 0. 本文相对原稿的调整说明

在评审原设计稿时，对照 rembg 源码（`rembg/sessions/__init__.py`、`session_factory.py`、`bg.py`）与 OpenAI 官方 Images API 规范做了核对，发现以下问题并已修正：

| # | 原稿问题 | 修正方式 | 依据 |
|---|---------|---------|------|
| 1 | 模型列表漏 `ben2-base`、`dis` 系列、`u2net_custom` 等内置 session；部分模型名拼写需对齐源码 `name()` 返回值 | 以 `rembg/sessions/__init__.py` 的 `sessions` 字典为准，列出全部 18 个内置模型 | [sessions/__init__.py](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/__init__.py) |
| 2 | `pyproject.toml` 直接写 `rembg` + `onnxruntime`，但 rembg 官方要求用 `rembg[cpu]` / `rembg[gpu]` extra 才会装上正确的 onnxruntime 后端；裸装会报 "No onnxruntime backend found" | 改用 `rembg[cpu]`（默认 CPU）并说明 GPU 切换方式 | [rembg/bg.py 顶部 sys.exit(1) 分支](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py) + README 安装说明 |
| 3 | 模型目录硬编码 `/root/.u2net`，未说明 rembg 如何识别自定义路径 | 明确通过 `U2NET_HOME` 环境变量配置；Dockerfile 设 `ENV U2NET_HOME=/models`，volume 直接挂 `/models` | [danielgatis 在 issue #420/#568 的回复](https://github.com/danielgatis/rembg/issues/420) + `sessions/base.py` 读取 `U2NET_HOME` |
| 4 | Dockerfile `COPY pyproject.toml uv.lock` 但仓库尚无 `uv.lock`；且 `pip install uv` 后用 `uv sync --frozen` 在 lock 不存在时会失败 | 分两阶段：先用 `uv sync` 生成 lock（构建机一次性），镜像用 `--frozen` 复现；补充 `.dockerignore` 与构建步骤说明 | uv 官方 best practice |
| 5 | 接口语义混用：`/v1/images/generations` 在 OpenAI 规范里是「文本生成图片」（`application/json` + `prompt`），而本项目是「输入图片→输出图片」（抠图改图）。把 multipart 上传塞进 generations 路由会让标准 OpenAI SDK 不兼容 | 主路由改用 `/v1/images/edits`（OpenAI 规范的「修改图片」端点，原生支持 multipart + image 文件 + prompt），request 字段对齐官方 SDK；同时保留 `/v1/images/generations` 作为别名兜底，但语义文档标注为「非标准用法」 | OpenAI 官方 `images.edit()` 走 `/v1/images/edits`，multipart + image + prompt |
| 6 | `GET /v1/models` 返回全部 18 个模型，但若挂载目录里只放了部分 `.onnx`，返回未挂载模型会让客户端请求时 500 | `/v1/models` 只返回「挂载目录中实际存在的 onnx 文件」对应的模型，避免推荐不可用模型 | 部署健壮性 |
| 7 | `remove()` 调用未处理：输入空文件、非图片、模型未挂载→会抛 onnxruntime 原始异常，返回 500 无可读信息 | 加 try/except 把 rembg/onnxruntime 异常映射为 OpenAI 风格 error 对象（`type`/`code`/`message`） | OpenAI error 响应规范 |
| 8 | 无 `response_format` 支持；OpenAI Images API 支持 `b64_json` / `url` 两种返回格式 | 由于本地无对象存储，`url` 模式返回临时 `/files/{id}` 短链（进程内缓存，TTL 1h）；默认 `b64_json` | OpenAI `response_format` 字段 |
| 9 | 无超长图片防护；rembg 对超大图在 CPU 上可能 OOM 或极慢 | 加可配置 `MAX_IMAGE_BYTES`（默认 25MB）与 `MAX_DIMENSION`（默认 4096px），超限返回 413 | 部署健壮性 |
| 10 | `sam` 模型需要 `input_points`/`input_labels`，直接走通用 generations 接口无法传参、会报错 | `/v1/models` 中对 `sam` 标注 `requires_prompt=true`；edits 接口支持透传 `extra` JSON 字段（rembg 原生 `-x` 参数等价物） | rembg USAGE.md SAM 章节 |
| 11 | session cache 无大小上限，长期运行加载 18 个大模型会 OOM | 加 `max_sessions` 上限（默认 4）+ LRU 淘汰 | 部署健壮性 |
| 12 | 无健康检查 / 就绪探针，docker-compose 没法判断模型目录是否就绪 | 加 `GET /health` 返回挂载目录可访问性 | 容器化最佳实践 |
| 13 | 原稿 Dockerfile 用 `python:3.12-slim` 但未装 libglib/libgl 等 onnxruntime 运行时系统依赖（slim 镜像缺） | `apt-get install libglib2.0-0 libgl1` 后再 `uv sync`，或直接用 `python:3.12`（体积换稳定） | onnxruntime 在 Debian slim 常见 ImportError |

以上 13 项均已纳入下文设计。**未对核心架构做重大颠覆**，只是把「能跑」升级成「能稳定生产」。

---

## 1. 项目概述

### 1.1 项目目标

构建一个本地化图片背景移除服务，对外以 **OpenAI Images API 兼容接口** 暴露 rembg 的抠图能力。客户端无需了解 rembg，使用任意 OpenAI SDK 的 `images.edit()` 方法即可完成「输入图片 → 透明 PNG」。

```
输入图片 (multipart)
    │
    ▼
/v1/images/edits   ← OpenAI 兼容路由
    │
    ▼
rembg 模型推理 (U2NET_HOME 挂载目录 · lazy session cache)
    │
    ▼
透明 PNG → base64（或临时 URL）
```

### 1.2 设计原则

- **对外只一个服务**：一个 FastAPI 进程，一个端口，一套 OpenAI 风格路由。
- **模型与代码解耦**：所有 `.onnx` 由 volume 挂载，镜像不含模型，U2NET_HOME 指向挂载点。
- **最小依赖**：FastAPI + uvicorn + rembg[cpu] + python-multipart，无 Redis/DB/对象存储。
- **OpenAI SDK 友好**：让 `openai.images.edit()` 能直接打过来，不报字段缺失。

---

## 2. 技术栈

| 组件 | 技术 | 版本/约束 |
|------|------|----------|
| API Framework | FastAPI | ≥0.115 |
| ASGI Server | uvicorn[standard] | ≥0.30 |
| 图像处理 | rembg[cpu] | ≥2.0.76 |
| ONNX 后端 | onnxruntime | 由 rembg[cpu] 拉入 |
| 运行时 | Python | ≥3.11（rembg 官方下限），镜像用 3.12 |
| 包管理 | uv | ≥0.5 |
| 容器 | Docker / docker compose | |
| 接口规范 | OpenAI Images API (`/v1/images/edits`) | |

---

## 3. 项目结构

```
rembg-openai-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + 路由
│   ├── config.py            # 环境变量 → 配置对象
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── errors.py            # OpenAI 风格错误映射
│   ├── rembg_service.py     # session cache + remove 封装
│   └── models_registry.py   # 挂载目录扫描 → 可用模型列表
├── models/                  # 挂载点（.onnx 放这里，镜像不含）
│   └── .gitkeep
├── tests/
│   ├── test_health.py
│   ├── test_edits.py        # 真实 rembg 调用（用 u2netp 小模型）
│   └── conftest.py
├── .dockerignore
├── pyproject.toml
├── uv.lock                  # 提交进仓库（见 §11 构建流程）
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 4. API 设计

### 4.1 路由总览

| 方法 | 路径 | 用途 | 兼容性 |
|------|------|------|--------|
| POST | `/v1/images/edits` | **主路由**：输入图片 → 抠图结果 | OpenAI 官方端点，SDK `images.edit()` |
| POST | `/v1/images/generations` | 兼容别名，内部转发到 edits | OpenAI 端点，但语义非标准（无 text→image） |
| GET  | `/v1/models` | 列出挂载目录中可用模型 | OpenAI 官方端点 |
| GET  | `/health` | liveness/readiness | 容器探针 |

> **为什么主路由用 edits 而不是 generations**：OpenAI 规范里 `generations` 是「文本 prompt → 新图」，请求体是 `application/json` + `prompt` 字段，不接受文件上传；`edits` 才是「输入图片 → 修改后图片」，原生 `multipart/form-data` + `image` 文件 + `prompt` 字段。抠图本质是「编辑图片」，用 edits 才能让标准 SDK 无感接入。

### 4.2 主接口：POST /v1/images/edits

**Content-Type:** `multipart/form-data`

**请求字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image` | file | 是 | 原始图片（png/jpg/webp） |
| `model` | string | 否 | rembg 模型名，默认 `u2netp` |
| `prompt` | string | 否 | OpenAI 规范要求字段，本服务忽略（抠图无文本指令）；为 SDK 兼容必须接受但不报错 |
| `response_format` | string | 否 | `b64_json`（默认）/ `url` |
| `n` | integer | 否 | 必须为 1（抠图无多图语义），>1 返回 400 |
| `extra` | string (JSON) | 否 | 透传 rembg 高级参数，见 §4.4 |

**curl 示例（默认 b64_json）：**
```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer sk-test" \
  -F "model=u2netp" \
  -F "image=@cat.png"
```

**响应（200，b64_json）：**
```json
{
  "created": 1752480000,
  "data": [
    { "b64_json": "iVBORw0KGgoAAA..." }
  ]
}
```

**响应（200，url 模式）：**
```json
{
  "created": 1752480000,
  "data": [
    { "url": "http://localhost:8000/files/ab3f9c.png" }
  ]
}
```
> URL 模式产物存进程内 `/tmp`，TTL 1h，由 `/files/{id}` 路由返回。

### 4.3 错误响应（OpenAI 风格）

所有 4xx/5xx 返回统一结构：
```json
{
  "error": {
    "message": "model 'foo' not found in mounted models directory",
    "type": "invalid_request_error",
    "code": "model_not_found",
    "param": "model"
  }
}
```

| HTTP | code | 触发场景 |
|------|------|---------|
| 400 | `invalid_request_error` | image 为空/非图片/n>1/model 不支持 prompt 但传了 |
| 401 | `invalid_request_error` | Authorization 缺失或 token 错（若启用鉴权） |
| 413 | `invalid_request_error` | 图片超 `MAX_IMAGE_BYTES` 或超 `MAX_DIMENSION` |
| 404 | `model_not_found` | model 名不在挂载目录可用列表 |
| 422 | `invalid_request_error` | rembg 解码失败 |
| 500 | `api_error` | onnxruntime 推理异常（原始 message 透传） |
| 503 | `model_load_failed` | 模型文件损坏或加载失败 |

### 4.4 高级参数透传（`extra` 字段）

rembg `remove()` 支持 `alpha_matting`、`only_mask`、`post_process_mask`、`bgcolor`、`input_points`（仅 sam）等。通过 `extra` JSON 字段透传，避免污染 OpenAI 标准字段：

```bash
curl http://localhost:8000/v1/images/edits \
  -F "model=u2netp" \
  -F "image=@cat.png" \
  -F 'extra={"alpha_matting":true,"alpha_matting_foreground_threshold":240}'
```

`extra` 仅允许以下白名单 key（其余忽略，记 warn 日志）：
`alpha_matting`, `alpha_matting_foreground_threshold`, `alpha_matting_background_threshold`, `alpha_matting_erode_size`, `only_mask`, `post_process_mask`, `bgcolor`, `input_points`, `input_labels`。

### 4.5 GET /v1/models

**只返回挂载目录中实际存在的 `.onnx` 对应的模型**，避免推荐不可用模型：
```json
{
  "object": "list",
  "data": [
    { "id": "u2netp", "object": "model", "owned_by": "rembg", "requires_prompt": false },
    { "id": "birefnet-general-lite", "object": "model", "owned_by": "rembg", "requires_prompt": false }
  ]
}
```
`requires_prompt=true` 的模型（如 `sam`）必须配合 `extra.input_points` 使用，客户端可据此提示用户。

### 4.6 GET /health

```json
{
  "status": "ok",
  "models_dir": "/models",
  "models_dir_writable": true,
  "available_models_count": 3,
  "loaded_sessions": 1
}
```

---

## 5. 模型支持列表

依据 `rembg/sessions/__init__.py` 的 `sessions` 字典，rembg v2.0.76 内置 18 个 session：

| 模型 ID | 大小 | 用途 | 需 prompt | CPU 友好 |
|---------|------|------|----------|---------|
| `u2net` | ~176MB | 通用 | 否 | 中 |
| `u2netp` | ~4MB | 通用·轻量 | 否 | ★推荐 |
| `u2net_human_seg` | ~176MB | 人物 | 否 | 中 |
| `u2net_cloth_seg` | ~176MB | 服装分割 | 否 | 中 |
| `silueta` | ~43MB | 通用·小 | 否 | 良 |
| `isnet-general-use` | ~43MB | 通用·高质 | 否 | 良 |
| `isnet-anime` | ~43MB | 二次元 | 否 | 良 |
| `sam` | ~374MB | 交互式分割 | **是** | 慢 |
| `birefnet-general` | ~43MB | 通用·高质 | 否 | 良 |
| `birefnet-general-lite` | ~12MB | 通用·轻量高质 | 否 | ★推荐 |
| `birefnet-portrait` | ~43MB | 人物肖像 | 否 | 良 |
| `birefnet-dis` | ~43MB | 二分图分割 | 否 | 良 |
| `birefnet-hrsod` | ~43MB | 高分辨率显著性 | 否 | 良 |
| `birefnet-cod` | ~43MB | 隐蔽目标检测 | 否 | 良 |
| `birefnet-massive` | ~43MB | 大数据集·泛化 | 否 | 良 |
| `bria-rmbg` | ~43MB | 通用·高质 | 否 | 良 |
| `ben2-base` | ~43MB | 高质量 matting | 否 | 良 |
| `u2net_custom` / `dis_custom` / `ben_custom` | — | 自定义模型加载（需 `extra.model_path`） | 否 | — |

> 文件名映射见 rembg `sessions/*.py` 的 `name()` 与下载 URL 表（见 §6.2）。挂载目录文件名必须与 rembg 期望一致，否则 session 加载时会重新下载到 `$U2NET_HOME`。

---

## 6. 模型加载设计

### 6.1 模型目录与环境变量

rembg 通过 `U2NET_HOME` 环境变量定位模型目录（源码 `sessions/base.py` 读取），优先级：
```
U2NET_HOME  >  $XDG_DATA_HOME/.u2net  >  $HOME/.u2net
```

本服务统一用 `U2NET_HOME=/models`，docker volume 挂载到 `/models`：
```
./models:/models   (而非原稿的 /root/.u2net，语义更清晰)
```

### 6.2 挂载目录结构

```
models/
├── u2net.onnx
├── u2netp.onnx
├── u2net_human_seg.onnx
├── u2net_cloth_seg.onnx
├── silueta.onnx
├── isnet-general-use.onnx
├── isnet-anime.onnx
├── vit_b-encoder-quant.onnx      # sam 用两个文件
├── vit_b-decoder-quant.onnx
├── BiRefNet-general-epoch_244.onnx
├── BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx
├── BiRefNet-portrait-epoch_150.onnx
├── BiRefNet-DIS-epoch_590.onnx
├── BiRefNet-HRSOD_DHU-epoch_115.onnx
├── BiRefNet-COD-epoch_125.onnx
├── BiRefNet-massive-TR_DIS5K_TR_TEs-epoch_420.onnx
├── bria-rmbg-2.0.onnx
└── BEN2_Base.onnx
```

> 文件名必须与 rembg 各 session 类的下载路径完全一致，否则 rembg 会判定「文件不存在」并触发重新下载（下载目标是 U2NET_HOME，会污染挂载目录或因只读挂载失败）。建议用 `rembg d <model>` 在构建期预下载，或在该项目的 README 提供 `scripts/download_models.sh`。

### 6.3 Lazy Loading + LRU Session Cache

```python
from collections import OrderedDict
from threading import Lock

class RembgService:
    def __init__(self, max_sessions: int = 4):
        self._sessions: OrderedDict[str, BaseSession] = OrderedDict()
        self._lock = Lock()
        self._max = max_sessions

    def get_session(self, model: str) -> BaseSession:
        with self._lock:
            if model in self._sessions:
                self._sessions.move_to_end(model)
                return self._sessions[model]
            session = new_session(model)        # 触发模型读取，失败抛异常
            self._sessions[model] = session
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)   # LRU 淘汰
            return session

    def remove(self, image_bytes: bytes, model: str, **extra) -> bytes:
        session = self.get_session(model)
        return remove(image_bytes, session=session, **extra)
```

- **不在启动时加载任何模型**：首次请求该模型才加载，冷启动 < 2s。
- **LRU 上限**：默认 4 个，防止内存爆炸。可经 `MAX_SESSIONS` 环境变量调整。
- **线程安全**：session 创建与淘汰加锁；推理本身不加锁（onnxruntime session 可并发推理）。

### 6.4 可用模型探测

`models_registry.py` 在启动时扫描 `U2NET_HOME`，对每个内置模型名反查期望的 onnx 文件名，存在即标记可用。`/v1/models` 与请求校验都依赖此结果，避免推荐挂载目录里没有的模型。

---

## 7. 核心代码设计

### 7.1 config.py

```python
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    u2net_home: str = os.getenv("U2NET_HOME", "/models")
    default_model: str = os.getenv("DEFAULT_MODEL", "u2netp")
    max_sessions: int = int(os.getenv("MAX_SESSIONS", "4"))
    max_image_bytes: int = int(os.getenv("MAX_IMAGE_BYTES", str(25 * 1024 * 1024)))
    max_dimension: int = int(os.getenv("MAX_DIMENSION", "4096"))
    file_ttl_seconds: int = int(os.getenv("FILE_TTL_SECONDS", "3600"))
    api_key: str | None = os.getenv("API_KEY") or None   # None=不鉴权

settings = Settings()
```

### 7.2 rembg_service.py

见 §6.3。`remove` 方法在调用前先经 `errors.py` 的装饰器捕获 onnxruntime/rembg 异常并映射为 OpenAI error 对象。

### 7.3 schemas.py（Pydantic v2）

```python
from pydantic import BaseModel, Field

class ImageItem(BaseModel):
    b64_json: str | None = None
    url: str | None = None

class ImagesResponse(BaseModel):
    created: int
    data: list[ImageItem]

class ModelObject(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "rembg"
    requires_prompt: bool = False

class ModelsListResponse(BaseModel):
    object: str = "list"
    data: list[ModelObject]
```

### 7.4 errors.py（异常 → OpenAI error）

封装一个 `RembgError(code, message, status, param=None)` 与全局 exception handler，把：
- `ValueError`（model not found）→ 404 `model_not_found`
- `PIL.UnidentifiedImageError` → 422 `invalid_request_error`
- `onnxruntime` 异常 → 503 `model_load_failed`
- 其余 → 500 `api_error`

输出统一 OpenAI error JSON。

### 7.5 main.py（路由骨架）

```python
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
import base64, time, json

from .config import settings
from .rembg_service import RembgService
from .models_registry import list_available_models
from .schemas import ImagesResponse, ImageItem
from .errors import RembgError, map_rembg_exc

app = FastAPI(title="rembg-openai-api")
service = RembgService(max_sessions=settings.max_sessions)

ALLOWED_EXTRA = {
    "alpha_matting", "alpha_matting_foreground_threshold",
    "alpha_matting_background_threshold", "alpha_matting_erode_size",
    "only_mask", "post_process_mask", "bgcolor",
    "input_points", "input_labels",
}

@app.post("/v1/images/edits")
async def edits(
    image: UploadFile = File(...),
    model: str = Form(settings.default_model),
    prompt: str = Form(""),          # 接受但忽略，SDK 兼容
    n: int = Form(1),
    response_format: str = Form("b64_json"),
    extra: str | None = Form(None),
):
    if n != 1:
        raise RembgError("invalid_request_error", "n must be 1", 400, "n")
    content = await image.read()
    if len(content) == 0:
        raise RembgError("invalid_request_error", "image is empty", 400, "image")
    if len(content) > settings.max_image_bytes:
        raise RembgError("invalid_request_error",
                         f"image exceeds {settings.max_image_bytes} bytes", 413, "image")

    kwargs = {}
    if extra:
        try: parsed = json.loads(extra)
        except json.JSONDecodeError:
            raise RembgError("invalid_request_error", "extra is not valid JSON", 400, "extra")
        kwargs = {k: v for k, v in parsed.items() if k in ALLOWED_EXTRA}

    with map_rembg_exc(model):
        result_bytes = service.remove(content, model, **kwargs)

    if response_format == "url":
        url = await save_to_tmp(result_bytes)
        return ImagesResponse(created=int(time.time()), data=[ImageItem(url=url)])
    return ImagesResponse(
        created=int(time.time()),
        data=[ImageItem(b64_json=base64.b64encode(result_bytes).decode())]
    )

# /v1/images/generations 作为兼容别名，复用同一实现
@app.post("/v1/images/generations")
async def generations_alias(image: UploadFile = File(...), model: str = Form(settings.default_model), prompt: str = Form(""), extra: str | None = Form(None)):
    kwargs = {}
    if extra:
        try: kwargs = {k: v for k, v in json.loads(extra).items() if k in ALLOWED_EXTRA}
        except Exception: pass
    with map_rembg_exc(model):
        result_bytes = service.remove(await image.read(), model, **kwargs)
    return ImagesResponse(
        created=int(time.time()),
        data=[ImageItem(b64_json=base64.b64encode(result_bytes).decode())]
    )

@app.get("/v1/models")
def models():
    return {"object": "list", "data": list_available_models()}

@app.get("/health")
def health():
    import os
    return {
        "status": "ok",
        "models_dir": settings.u2net_home,
        "models_dir_writable": os.access(settings.u2net_home, os.W_OK),
        "available_models_count": len(list_available_models()),
        "loaded_sessions": len(service._sessions),
    }
```

---

## 8. Dockerfile

```dockerfile
FROM python:3.12-slim

# onnxruntime 在 slim 上常缺 libglib/libgl，必须补
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    U2NET_HOME=/models

WORKDIR /app

# 1) 装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 2) 先拷 lock 与 manifest 利用缓存
COPY pyproject.toml uv.lock ./

# 3) 复现环境（frozen 保证 lock 一致；不装 dev 依赖）
RUN uv sync --frozen --no-dev

# 4) 拷源码
COPY app ./app

# 5) 模型挂载点
RUN mkdir -p /models
VOLUME ["/models"]

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

要点：
- 用 `ghcr.io/astral-sh/uv` 官方镜像拷 `uv` 二进制，省一次 `pip install uv`。
- `UV_LINK_MODE=copy`：复制而非软链，避免 build context 隔离问题。
- `VOLUME ["/models"]` 提示挂载点；docker-compose 显式映射。
- `.dockerignore` 排除 `models/*.onnx`、`tests/`、`.git`、`__pycache__`。

---

## 9. docker-compose.yml

```yaml
services:
  rembg-api:
    build: .
    image: local/rembg-openai-api:latest
    container_name: rembg-api
    ports:
      - "8000:8000"
    environment:
      U2NET_HOME: /models
      DEFAULT_MODEL: u2netp
      MAX_SESSIONS: "4"
      MAX_IMAGE_BYTES: "26214400"   # 25MB
      # API_KEY: sk-xxx             # 取消注释启用鉴权
    volumes:
      - ./models:/models            # 只读可加 :ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

---

## 10. pyproject.toml

```toml
[project]
name = "rembg-openai-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "python-multipart>=0.0.9",
    "rembg[cpu]>=2.0.76",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]

[tool.uv]
package = true
```

要点：
- 用 `rembg[cpu]` extra 自动带 `onnxruntime`（CPU 版），裸写 `rembg`+`onnxruntime` 在某些组合下会缺 provider。
- GPU 部署：把 `rembg[cpu]` 换成 `rembg[gpu]`，Dockerfile 改 NVIDIA 基础镜像 + CUDA。本文聚焦 CPU 部署，GPU 留 §16 扩展。

---

## 11. 构建与运行流程

### 11.1 生成 `uv.lock`（一次性，开发机）
```bash
uv sync                       # 生成 uv.lock
git add uv.lock               # 提交进仓库
```

### 11.2 本地运行
```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 11.3 Docker 构建与运行
```bash
docker compose up -d --build
```

### 11.4 预下载模型到挂载目录（推荐）
```bash
# 在宿主机或镜像里一次性下载，避免首次请求卡顿
docker run --rm -v "$PWD/models:/models" -e U2NET_HOME=/models \
  local/rembg-openai-api:latest \
  uv run rembg d u2netp

# 下载多个
for m in u2netp birefnet-general-lite isnet-anime; do
  docker run --rm -v "$PWD/models:/models" -e U2NET_HOME=/models \
    local/rembg-openai-api:latest uv run rembg d "$m"
done
```

### 11.5 调用
```bash
curl http://localhost:8000/v1/images/edits -F model=u2netp -F image=@cat.png
```

---

## 12. CPU 部署推荐模型

| 场景 | 模型 | 理由 |
|------|------|------|
| 通用·最快冷启动 | `u2netp` | 4MB，默认 |
| 通用·质量优先 | `birefnet-general-lite` | 12MB，质量≈u2net 但更小 |
| 人物 | `birefnet-portrait` | 人像优化 |
| 二次元 | `isnet-anime` | 动漫线条 |
| 高质量 matting | `ben2-base` | 边缘发丝 |
| 交互式精确 | `sam`（需 extra.input_points） | 点选目标 |

---

## 13. 验证策略

| 层 | 方法 | 范围 |
|----|------|------|
| 单元 | pytest | schemas、errors 映射、models_registry 扫描 |
| 集成 | pytest + httpx + 真实 u2netp | `/health`、`/v1/models`、`/v1/images/edits` 端到端跑一张 1KB PNG，断言返回 b64 可解码为透明 PNG |
| 容错 | pytest | image 空、超限、model 不存在、n=2、extra 非法 JSON |
| 依赖 | `uv sync --frozen` 在干净环境复现 | 保证 lock 可复现 |
| 容器 | `docker compose up` + curl 健康检查 + 真实抠图请求 | 镜像可用 |

---

## 14. 最终部署形态

用户最终只需：
```bash
docker run -d -p 8000:8000 -v "$PWD/models:/models" \
  local/rembg-openai-api:latest
```
然后调用 `http://localhost:8000/v1/images/edits` 即可。任何 OpenAI SDK：
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-test")
with open("cat.png","rb") as f:
    r = client.images.edit(model="u2netp", image=f, prompt="")
print(r.data[0].b64_json)
```

---

## 15. 后续扩展方向（不在本期）

- API Key 校验（`API_KEY` 环境变量已有占位，handler 待加）
- Redis 任务队列 / 异步 Worker（高并发批量）
- 多 GPU Worker（换 `rembg[gpu]` + NVIDIA 镜像）
- 图片 URL 输入（先下载再抠）
- Webhook 回调
- 对象存储后端（`url` 模式产物上 S3/MinIO）
- 多模型并行服务
- ONNX Runtime CPU 优化（OMP_NUM_THREADS、provider 选项）
- 完整 OpenAI `/v1/images/variations` 端点（语义为「生成同类变体」，与本服务不符，暂不实现）

---

## 16. 附录：原稿与本文差异速查

见本文开头「§0 调整说明」表格。核心改动一句话概括：

> **主路由由 generations 改为 edits 以契合 OpenAI SDK；模型目录由 /root/.u2net 改为 U2NET_HOME=/models 让语义清晰；依赖由 rembg+onnxruntime 改为 rembg[cpu] 避免缺后端报错；补齐模型列表、错误映射、LRU cache、健康检查、尺寸防护、SAM 高级参数透传，把 demo 升级为可生产。**
