# DocsCool Contract Manager

前后端分离合同管理系统，适配 Synology NAS：
- 文件存储在共享目录，按部门子目录落盘，复用 NAS 权限管理。
- 登录直接校验 Synology DSM 账号密码，不维护本地用户表。
- 结构化合同数据存储在 SQLite。
- 支持 PDF 预览、AI OCR/解析、远程 FileStation 上传下载。

## 目录结构

- `backend`: Flask API + SQLite
- `frontend`: Vue3 + Element Plus
- `docker-compose.yml`: 一键部署

## 后端环境变量

编辑 `backend/.env`：

- `SYNOLOGY_BASE_URL`: DSM 地址，例如 `https://192.168.1.10:5001`
- `SYNOLOGY_VERIFY_SSL`: 内网自签名证书通常设置为 `false`
- `CONTRACT_STORAGE_MODE`: `local` 或 `remote`
- `CONTRACT_STORAGE_ROOT`: 合同根目录，例如 `/volume1/contracts`
- `SYNOLOGY_FILESTATION_ROOT`: 群晖 FileStation 中的共享目录路径，例如 `/contracts`
- `SYNOLOGY_UPLOAD_ACCOUNT` / `SYNOLOGY_UPLOAD_PASSWORD`: 远程上传到 NAS 时使用的 DSM 账号
- `MINIMAX_API_KEY`: 启用 AI 识别时必填

推荐参考 [backend/.env.example](backend/.env.example) 完成配置。

## Synology 侧准备

1. 在 DSM 中安装 `Container Manager`。
2. 创建共享文件夹用于存放合同文件，例如 `contracts` 或 `沿海管道/合同管理`。
3. 在该共享目录下预建部门子目录，例如 `法务部`、`采购部`、`工程部`。
4. 为实际使用系统的 DSM 用户分配这些目录的访问权限。
5. 准备一个有 FileStation 上传权限的 DSM 账号，用于 `SYNOLOGY_UPLOAD_ACCOUNT`。
6. 确认 DSM 的 HTTPS 地址可以从容器访问，例如 `https://NAS_IP:5001`。

## 部署方式选择

本项目支持两种 NAS 存储模式：

### 1. `remote` 模式

- 合同文件通过 FileStation API 直接上传到 NAS。
- 适合当前项目默认部署方式。
- 需要配置：
	- `SYNOLOGY_BASE_URL`
	- `SYNOLOGY_FILESTATION_ROOT`
	- `SYNOLOGY_UPLOAD_ACCOUNT`
	- `SYNOLOGY_UPLOAD_PASSWORD`

### 2. `local` 模式

- 后端容器直接写挂载进来的 NAS 目录。
- 需要把共享目录挂载到容器内，并确保容器内路径与 `CONTRACT_STORAGE_ROOT` 一致。

## 在 NAS 上部署

以下步骤适用于 Synology DSM 7.x + Container Manager。

### 1. 上传项目文件

将整个项目目录上传到 NAS，例如：

- `/volume1/docker/docscool`

目录下应至少包含：

- `docker-compose.yml`
- `backend/`
- `frontend/`
- `README.md`

### 2. 配置后端环境变量

编辑 `backend/.env`，至少确认以下参数：

```dotenv
FLASK_ENV=production
APP_SECRET_KEY=RandomSecret
DATABASE_URL=sqlite:///instance/contracts.db

SYNOLOGY_BASE_URL=https://NAS_URL:5001
SYNOLOGY_VERIFY_SSL=false

CONTRACT_STORAGE_MODE=remote
CONTRACT_STORAGE_ROOT=/volume1/contracts
SYNOLOGY_FILESTATION_ROOT=/contracts

SYNOLOGY_UPLOAD_ACCOUNT=DSM Account
SYNOLOGY_UPLOAD_PASSWORD=DSM Password
SYNOLOGY_UPLOAD_SESSION=FileStation

MINIMAX_API_KEY=KEY_STRING
MINIMAX_API_URL=https://api.minimaxi.com/v1/chat/completions
MINIMAX_MODEL=MiniMax-M2.5
MY_COMP=My_Company_Name
```

说明：

- 如果不用 AI 解析，可先留空 `MINIMAX_API_KEY`。
- `SYNOLOGY_FILESTATION_ROOT` 要写 FileStation 视角下的路径，不是 Linux 挂载路径。
- 例如共享目录真实路径是 `/volume1/contracts`，则 FileStation 路径通常写 `/contracts`。

### 3. 配置 `docker-compose.yml` 参数（推荐）

当前 [docker-compose.yml](docker-compose.yml) 已支持通过环境变量配置：

- `DOCSCOOL_STORAGE_HOST_PATH`: NAS 主机上的合同目录（例如 `/volume1/contracts`）
- `DOCSCOOL_BACKEND_PORT`: 后端映射端口（默认 `5000`）
- `DOCSCOOL_FRONTEND_PORT`: 前端映射端口（默认 `8080`）
- `DOCSCOOL_BACKEND_CONTAINER` / `DOCSCOOL_FRONTEND_CONTAINER`: 容器名

可直接复制 [ .env.compose.example ](.env.compose.example) 为根目录 `.env` 后按需修改：`cp .env.compose.example .env`

建议在项目根目录（与 [docker-compose.yml](docker-compose.yml) 同级）创建 `.env`：

```dotenv
DOCSCOOL_STORAGE_HOST_PATH=/volume1/contracts
DOCSCOOL_BACKEND_PORT=5000
DOCSCOOL_FRONTEND_PORT=8080
DOCSCOOL_BACKEND_CONTAINER=contract-backend
DOCSCOOL_FRONTEND_CONTAINER=contract-frontend
```

说明：

- `DOCSCOOL_STORAGE_HOST_PATH` 建议与 `backend/.env` 里的 `CONTRACT_STORAGE_ROOT` 指向同一目录。
- `remote` 模式下建议仍保留该挂载用于路径兼容。
- `local` 模式下该挂载是必需项。

### 4. 用 Container Manager 创建项目

在 DSM 中打开 `Container Manager`：

1. 进入 `项目`。
2. 点击 `新增`。
3. 选择项目目录，例如 `/volume1/docker/docscool`。
4. 选择使用已有的 `docker-compose.yml`。
5. 启动项目。

启动后会创建两个容器：

- `contract-backend`
- `contract-frontend`

### 5. 访问系统

- 前端地址：`http://NAS_IP:${DOCSCOOL_FRONTEND_PORT:-8080}`
- 后端健康检查：`http://NAS_IP:${DOCSCOOL_BACKEND_PORT:-5000}/api/health`

如果健康检查返回：

```json
{"status":"ok"}
```

说明后端已正常启动。

### 6. 界面化快速部署手册

如果你希望按 DSM 界面逐步点击部署，可直接参考：

- [docs/群晖界面截图式部署手册.md](docs/群晖界面截图式部署手册.md)

## 首次部署后的检查项

1. 使用 DSM 账号登录系统，确认可以成功登录。
2. 新建一条合同并上传 PDF，确认上传成功。
3. 打开合同编辑框，确认 PDF 可以预览。
4. 测试合同下载，确认能从 NAS 正常取回文件。
5. 测试 AI 解析，确认接口密钥和超时时间配置正常。

## 常见问题

### 1. 前端能打开，但无法登录

优先检查：

- `SYNOLOGY_BASE_URL` 是否可从容器访问
- DSM 账号密码是否正确
- DSM 是否开启 5001 HTTPS 访问
- 自签名证书场景下 `SYNOLOGY_VERIFY_SSL` 是否为 `false`

### 2. 上传或预览失败

优先检查：

- `SYNOLOGY_FILESTATION_ROOT` 是否写对
- `SYNOLOGY_UPLOAD_ACCOUNT` 是否有共享目录权限
- NAS 中目标目录是否真实存在
- 合同文件所在部门目录是否已创建

### 3. 页面能打开，但没有合同数据

SQLite 数据库存放在：

- `backend/instance/contracts.db`

如果你重建项目或替换目录，请确保这个目录被保留。

### 4. AI 解析失败

优先检查：

- `MINIMAX_API_KEY` 是否有效
- NAS 是否能访问外网 AI 接口
- 上传文件是否为可识别的 PDF

## 本地开发启动

### Backend

```bash
cd backend
pip install -r requirements.txt
python run.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:5173`

## Docker 部署（推荐群晖）

```bash
docker compose up -d --build
```

访问前端：`http://NAS_IP:${DOCSCOOL_FRONTEND_PORT:-8080}`

如果是在 NAS Shell 中执行，建议进入项目目录后运行上述命令。

## 主要接口

- `GET /api/health` 健康检查
- `POST /api/auth/login` DSM 账号登录
- `GET /api/auth/me` 获取当前登录用户
- `GET /api/contracts` 查询合同（支持筛选）
- `POST /api/contracts` 新建合同
- `PUT /api/contracts/<id>` 更新合同
- `POST /api/contracts/<id>/upload` 上传合同文件
- `GET /api/contracts/<id>/download` 下载原文件
- `GET /api/contracts/<id>/preview` 在线预览 PDF
- `POST /api/contracts/ai-parse` AI 解析 PDF
- `GET /api/settings/departments` 部门列表
- `POST /api/settings/departments` 新增部门
- `DELETE /api/settings/departments/<id>` 删除部门
- `GET /api/settings/projects` 项目列表
- `POST /api/settings/projects` 新增项目
- `DELETE /api/settings/projects/<id>` 删除项目
- `GET /api/options/contract-fields` 合同字段选项

## 说明

系统不保存用户密码，不创建本地用户体系；仅在登录时调用 DSM 认证接口校验账号。
