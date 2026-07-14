# Rembg OpenAI Image API Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 本地 FastAPI 服务，OpenAI Images 兼容接口调用 rembg 抠图，Docker + uv + 外部模型挂载。

**Architecture:** FastAPI 暴露 `/v1/images/edits`（主）与 `/v1/images/generations`（别名）；`RembgService` lazy + LRU session；`U2NET_HOME=/models` 挂载 onnx；`/v1/models` 只列可用模型。

**Tech Stack:** Python 3.12, FastAPI, uvicorn, rembg[cpu], uv, Docker

## Global Constraints

- requires-python `>=3.11`，镜像 Python 3.12
- 依赖：`fastapi`, `uvicorn[standard]`, `python-multipart`, `rembg[cpu]`
- 模型目录：`U2NET_HOME` 默认 `/models`
- 默认模型：`u2netp`
- 对外端口：`8000`
- 与用户交互中文；不主动 commit
- ponytail：无 Redis/DB/对象存储；`response_format=url` 本期跳过（仅 b64_json）；API Key 本期跳过

## File Map

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | 依赖与包元数据 |
| `app/config.py` | 环境变量配置 |
| `app/errors.py` | OpenAI 风格错误 |
| `app/schemas.py` | 响应模型 |
| `app/models_registry.py` | 扫描可用模型 |
| `app/rembg_service.py` | session cache + remove |
| `app/main.py` | 路由 |
| `tests/*` | 行为测试 |
| `Dockerfile` / `docker-compose.yml` | 容器 |
| `README.md` | 使用说明 |

---

### Task 1: 项目脚手架 + 配置

**Files:**
- Create: `pyproject.toml`, `app/__init__.py`, `app/config.py`, `models/.gitkeep`, `.dockerignore`
- Test: `tests/test_config.py`

**Produces:** `Settings` dataclass，`settings` 单例

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
from app.config import Settings

def test_defaults():
    s = Settings(_env={})
    assert s.default_model == "u2netp"
    assert s.u2net_home == "/models"
    assert s.max_sessions == 4
```

- [ ] **Step 2: 实现 config + pyproject，使测试通过**

- [ ] **Step 3: `uv sync` 装依赖**

---

### Task 2: errors + schemas

**Files:**
- Create: `app/errors.py`, `app/schemas.py`
- Test: `tests/test_errors.py`

**Produces:** `RembgError`, `openai_error_handler`, `ImagesResponse`, `ModelObject`

- [ ] **Step 1: 测试 error JSON 形状**
- [ ] **Step 2: 最小实现**

---

### Task 3: models_registry

**Files:**
- Create: `app/models_registry.py`
- Test: `tests/test_models_registry.py`

**Produces:** `list_available_models(models_dir) -> list[ModelObject]`

- [ ] **Step 1: 用临时目录测「有 onnx 才列出」**
- [ ] **Step 2: 实现文件名→模型 ID 映射（对齐 rembg）**

---

### Task 4: rembg_service

**Files:**
- Create: `app/rembg_service.py`
- Test: `tests/test_rembg_service.py`（mock `new_session`/`remove`）

**Produces:** `RembgService.get_session`, `RembgService.remove`

- [ ] **Step 1: 测 LRU 淘汰与 session 复用**
- [ ] **Step 2: 最小实现**

---

### Task 5: FastAPI 路由

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`（httpx + TestClient，mock service）

**Produces:**
- `POST /v1/images/edits`
- `POST /v1/images/generations`（别名）
- `GET /v1/models`
- `GET /health`

- [ ] **Step 1: health / models / edits 失败测试**
- [ ] **Step 2: 实现路由 + 校验（空图、n!=1、未知 model、超限）**

---

### Task 6: Docker + README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `README.md`

- [ ] **Step 1: Dockerfile（uv frozen + slim 系统库）**
- [ ] **Step 2: compose + README 用法**

---

### Task 7: 端到端验证

- [ ] **Step 1: `uv run pytest` 全绿**
- [ ] **Step 2: 若有 uv.lock 则 `uv sync --frozen` 可复现**
- [ ] **Step 3: 交付 diff 摘要**

## Spec coverage checklist

- [x] OpenAI edits 主路由 + generations 别名
- [x] lazy + LRU session
- [x] U2NET_HOME 挂载
- [x] /v1/models 仅可用模型
- [x] OpenAI error 形状
- [x] MAX_IMAGE_BYTES / n=1 / empty image
- [x] extra 白名单透传
- [x] Docker + compose
- [ ] response_format=url — YAGNI 跳过
- [ ] API_KEY — YAGNI 跳过
