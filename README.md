# rembg-openai-api

本地 rembg 抠图服务，OpenAI Images API 兼容接口。

## 依赖说明

- Python ≥3.11（推荐 3.12）
- `rembg[cpu]` 经 `pymatting` 会拉旧 `numba`；本项目显式 pin `numba>=0.60` 以兼容 Python 3.12

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 准备模型（至少 u2netp）
uv run models list
uv run models pull u2netp
# 或: uv run models pull --all

# 3. 启动
U2NET_HOME=./models uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
# 生成 lock 后构建
uv sync
docker compose up -d --build

# 查看支持的模型
docker run --rm -v "$PWD/models:/models" -e U2NET_HOME=/models \
  local/rembg-openai-api:latest models list

# 拉取指定模型
docker run --rm -v "$PWD/models:/models" -e U2NET_HOME=/models \
  local/rembg-openai-api:latest models pull u2netp

# 拉取全部可下载模型
docker run --rm -v "$PWD/models:/models" -e U2NET_HOME=/models \
  local/rembg-openai-api:latest models pull --all
```

### 镜像发布（GitHub Actions → GHCR）

推送到 `ghcr.io/<owner>/rembg-openai-api`。镜像 tag：`{项目版本}-rembg{rembg版本}` + `latest`。

| 来源 | 取值 |
|------|------|
| 项目版本 | git tag `v0.1.0` → `0.1.0`；否则读 `pyproject.toml` |
| rembg 版本 | `uv.lock` 锁定版本（可复现） |

| 触发 | 行为 |
|------|------|
| `git tag v0.1.0 && git push origin v0.1.0` | 构建并推送 `0.1.0-rembg…`、`latest` |
| Actions → **Docker** → Run workflow | 同上（基于当前分支） |
| Actions → **Update rembg**（定时每天 UTC 03:00 / 手动） | `uv lock --upgrade-package rembg`；有变化则提交 `uv.lock` 并自动构建镜像 |

```bash
# 拉取（仓库需允许 packages 读取；私有包先 docker login ghcr.io）
docker pull ghcr.io/<owner>/rembg-openai-api:latest
docker pull ghcr.io/<owner>/rembg-openai-api:0.1.0-rembg2.0.76
```

说明：自动升级只改 `uv.lock`，不改业务代码。默认分支若开了 branch protection，需允许 `github-actions[bot]` 推送，或改成开 PR。

## 模型 CLI

容器内 / 本地统一入口 `models`：

| 命令 | 说明 |
|------|------|
| `models list` | 列出支持模型及是否已安装 |
| `models pull <id> [...]` | 拉取指定模型 |
| `models pull --all` | 拉取全部可自动下载的模型 |

目录默认 `$U2NET_HOME`（容器内 `/models`），可用 `--dir` 覆盖（会解析为绝对路径）。

### 下载代理（国内网络）

rembg 模型从 GitHub Releases 拉取。可任选：

```bash
# 1) GitHub 镜像前缀（推荐）
export GITHUB_PROXY=https://gh-proxy.com/
# 别名: GITHUB_RELEASES_PROXY
uv run models pull u2netp --dir ./models

# 2) 通用 HTTPS 代理（urllib/pooch 原生支持）
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
uv run models pull u2netp --dir ./models
```

`GITHUB_PROXY` 会把  
`https://github.com/...`  
改写成  
`https://gh-proxy.com/https://github.com/...`  
（也可换成其他同类镜像前缀）。

## API

### 抠图（主路由）

支持两种请求体：

**1. multipart 文件上传**

```bash
curl http://localhost:8000/v1/images/edits \
  -F model=u2netp \
  -F image=@cat.png \
  -F prompt=
```

**2. JSON（`image` = base64 或 URL）**

```bash
# base64
curl http://localhost:8000/v1/images/edits \
  -H 'Content-Type: application/json' \
  -d '{"model":"u2netp","image":"iVBORw0KGgo...","response_format":"b64_json"}'

# 也支持 data URL
# "image": "data:image/png;base64,iVBORw0KGgo..."

# 或图片 URL
curl http://localhost:8000/v1/images/edits \
  -H 'Content-Type: application/json' \
  -d '{"model":"u2netp","image":"https://example.com/cat.png"}'
```

`response_format` 默认 `b64_json`。

响应：

```json
{
  "created": 1752480000,
  "data": [{ "b64_json": "..." }]
}
```

### 兼容别名

`POST /v1/images/generations` 同 edits。

### 模型列表

```bash
curl http://localhost:8000/v1/models
```

仅返回 `./models`（或 `U2NET_HOME`）中实际存在的模型。

### 健康检查

```bash
curl http://localhost:8000/health
```

## OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-test")
with open("cat.png", "rb") as f:
    r = client.images.edit(model="u2netp", image=f, prompt="")
print(r.data[0].b64_json[:40])
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `U2NET_HOME` | `/models` | rembg 模型目录 |
| `DEFAULT_MODEL` | `u2netp` | 未传 model 时使用 |
| `MAX_SESSIONS` | `4` | LRU session 上限 |
| `MAX_IMAGE_BYTES` | `26214400` | 上传大小上限（25MB） |
| `MAX_DIMENSION` | `4096` | 单边像素上限 |
| `FILE_TTL_SECONDS` | `3600` | `response_format=url` 临时文件 TTL |
| `MAX_FILE_STORE_ITEMS` | `64` | url 模式内存缓存条数上限（LRU） |
| `MAX_FILE_STORE_BYTES` | `268435456` | url 模式内存缓存总字节上限（256MB） |
| `MAX_CONCURRENT` | `2` | 同时进行的抠图推理数 |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | url 模式返回的前缀 |
| `API_KEY` | 空 | 设置后启用 `Authorization: Bearer` 鉴权（`/health` 除外） |

## response_format

- `b64_json`（默认）：返回 base64 PNG
- `url`：返回临时链接 `/files/{id}`，TTL 见 `FILE_TTL_SECONDS`

```bash
curl http://localhost:8000/v1/images/edits \
  -F model=u2netp -F image=@cat.png -F response_format=url
```

## 鉴权

```bash
export API_KEY=sk-secret
# 请求时：
curl -H "Authorization: Bearer sk-secret" ...
```

## 推荐模型（CPU）

模型列表来自当前安装的 rembg（`sessions_names`，排除 `*_custom`），随 rembg 升级自动变化。

| 场景 | model |
|------|------|
| 默认/最快 | `u2netp` |
| 质量优先 | `birefnet-general-lite` |
| 人物 | `birefnet-portrait` |
| 二次元 | `isnet-anime` |

## 高级参数

通过 `extra` JSON 透传 rembg 参数（白名单）：

```bash
curl http://localhost:8000/v1/images/edits \
  -F model=u2netp \
  -F image=@cat.png \
  -F 'extra={"post_process_mask":true}'
```

## 测试

```bash
uv sync --group dev
uv run pytest -v
```
