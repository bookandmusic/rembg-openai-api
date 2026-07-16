# rembg-openai-api

基于 [rembg](https://github.com/danielgatis/rembg) 的本地抠图服务。去掉图片背景，输出透明 PNG。接口兼容 OpenAI Images API，可用 OpenAI SDK 直接对接。

- 主接口：`POST /v1/images/edits`
- 镜像：`ghcr.io/bookandmusic/rembg-openai-api`（`latest` 或 `{版本}-rembg{rembg版本}`，如 `0.1.0-rembg2.0.76`）

## 快速开始

新建目录，保存为 `docker-compose.yml`（仓库根目录那份仅用于本地构建，部署请用下面这份）：

```yaml
services:
  rembg-api:
    image: ghcr.io/bookandmusic/rembg-openai-api:latest
    container_name: rembg-api
    ports:
      - "8000:8000"
    environment:
      PUBLIC_BASE_URL: http://localhost:8000
      # API_KEY: sk-xxx
      # GITHUB_PROXY: https://gh-proxy.com/   # 国内拉模型时取消注释
    volumes:
      - ./models:/models
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

```bash
mkdir -p models
docker compose pull && docker compose up -d

# 首次必须拉模型，否则抠图 404（model_not_found）
docker compose exec rembg-api models pull u2netp

# 抠图并保存为 out.png（默认返回 base64）
curl -s http://localhost:8000/v1/images/edits -F image=@cat.png \
  | jq -r '.data[0].b64_json' | base64 -d > out.png
```

健康检查：`curl http://localhost:8000/health`  
已装模型：`curl http://localhost:8000/v1/models`

### 纯 Docker

```bash
mkdir -p models
docker pull ghcr.io/bookandmusic/rembg-openai-api:latest
docker run -d --name rembg-api \
  -p 8000:8000 \
  -v "$PWD/models:/models" \
  -e PUBLIC_BASE_URL=http://localhost:8000 \
  ghcr.io/bookandmusic/rembg-openai-api:latest
docker exec rembg-api models pull u2netp
```

模型目录默认 `/models`（`U2NET_HOME`），挂载 `./models:/models` 即可持久化。  
公网访问时把 `PUBLIC_BASE_URL` 改成对外地址（影响 `response_format=url` 的链接前缀）。

## 模型

| 命令 | 说明 |
|------|------|
| `models list` | 列出支持模型及安装状态 |
| `models pull <id> [...]` | 拉取指定模型 |
| `models pull --all` | 拉取全部可自动下载的模型 |

未安装的模型不会出现在 `GET /v1/models`。

### 国内网络

模型从 GitHub Releases 下载，代理须设在**容器内**（compose `environment` 或 `docker exec -e`）。宿主机 `export` 不会进入已运行容器。

```bash
docker compose exec -e GITHUB_PROXY=https://gh-proxy.com/ rembg-api models pull u2netp
# 也可设 HTTPS_PROXY / HTTP_PROXY
```

### 推荐（CPU）

| 场景 | model |
|------|------|
| 默认 / 最快 | `u2netp` |
| 质量优先 | `birefnet-general-lite` |
| 人物 | `birefnet-portrait` |
| 二次元 | `isnet-anime` |

## API

| 路径 | 说明 |
|------|------|
| `POST /v1/images/edits` | 抠图 |
| `POST /v1/images/generations` | 别名，行为同 edits |
| `GET /v1/models` | 已安装模型 |
| `GET /health` | 健康检查 |
| `GET /files/{id}` | 临时结果文件 |

### 请求

支持两种 Content-Type：

| Content-Type | `image` 取值 |
|--------------|--------------|
| `multipart/form-data` | 文件上传 |
| `application/json` | raw base64、data URL 或 http(s) URL |

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `image` | 是 | — | 待抠图 |
| `model` | 否 | `u2netp` | 须已 `models pull` |
| `response_format` | 否 | `b64_json` | `b64_json` 或 `url` |
| `n` | 否 | `1` | 仅支持 `1` |
| `prompt` | 否 | `""` | 兼容 OpenAI SDK，内容忽略 |
| `extra` | 否 | — | JSON 对象，透传 rembg 参数（见下表） |

`extra` 白名单：

| 字段 | 说明 |
|------|------|
| `alpha_matting` | 启用 alpha matting |
| `alpha_matting_foreground_threshold` | 前景阈值 |
| `alpha_matting_background_threshold` | 背景阈值 |
| `alpha_matting_erode_size` | 腐蚀尺寸 |
| `only_mask` | 仅输出 mask |
| `post_process_mask` | 后处理 mask |
| `bgcolor` | 背景色 |
| `input_points` | SAM 点坐标（`sam` 模型需要） |
| `input_labels` | SAM 点标签（`sam` 模型需要） |

multipart 示例：

```bash
curl http://localhost:8000/v1/images/edits \
  -F image=@cat.png \
  -F model=u2netp \
  -F response_format=b64_json \
  -F 'extra={"post_process_mask":true}'
```

JSON 示例：

```bash
curl http://localhost:8000/v1/images/edits \
  -H 'Content-Type: application/json' \
  -d '{"image":"https://example.com/cat.png","model":"u2netp"}'
```

### 响应

| 字段 | 说明 |
|------|------|
| `created` | Unix 时间戳 |
| `data` | 结果数组，长度为 `n`（固定 1） |
| `data[].b64_json` | 透明 PNG 的 base64（`response_format=b64_json`） |
| `data[].url` | 临时下载链接（`response_format=url`，前缀为 `PUBLIC_BASE_URL`，TTL 见 `FILE_TTL_SECONDS`） |

`b64_json`：

```json
{
  "created": 1752480000,
  "data": [{ "b64_json": "iVBORw0KGgo..." }]
}
```

`url`：

```json
{
  "created": 1752480000,
  "data": [{ "url": "http://localhost:8000/files/...." }]
}
```

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-test")
with open("cat.png", "rb") as f:
    r = client.images.edit(model="u2netp", image=f, prompt="")
print(r.data[0].b64_json[:40])
```

### 鉴权

设置 `API_KEY` 后，除 `/health` 外需 `Authorization: Bearer <key>`。

## 环境变量

默认值一般够用；公网建议配置 `PUBLIC_BASE_URL` 与 `API_KEY`。

| 变量 | 默认 | 说明 |
|------|------|------|
| `U2NET_HOME` | `/models` | 模型目录 |
| `DEFAULT_MODEL` | `u2netp` | 默认模型 |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | url 模式链接前缀 |
| `API_KEY` | 空 | Bearer 鉴权 |
| `GITHUB_PROXY` | 空 | 模型下载镜像前缀（容器内） |
| `MAX_CONCURRENT` | `2` | 同时推理数 |
| `MAX_SESSIONS` | `4` | LRU session 上限 |
| `MAX_IMAGE_BYTES` | `26214400` | 上传上限（25MB） |
| `MAX_DIMENSION` | `4096` | 单边像素上限 |
| `FILE_TTL_SECONDS` | `3600` | 临时文件 TTL |
| `MAX_FILE_STORE_ITEMS` | `64` | 临时文件条数上限 |
| `MAX_FILE_STORE_BYTES` | `268435456` | 临时文件总字节上限 |
