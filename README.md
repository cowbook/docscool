# DocsCool Contract Manager

前后端分离合同管理系统，适配 Synology NAS：
- 文件存储在共享目录，按部门子目录落盘，复用 NAS 权限管理。
- 登录直接校验 Synology DSM 账号密码，不维护本地用户表。
- 结构化合同数据存储在 SQLite。

## 目录结构

- `backend`: Flask API + SQLite
- `frontend`: Vue3 + Element Plus
- `docker-compose.yml`: 一键部署

## 后端环境变量

编辑 `backend/.env`：

- `SYNOLOGY_BASE_URL`: DSM 地址，例如 `https://192.168.1.10:5001`
- `SYNOLOGY_VERIFY_SSL`: 内网自签名证书通常设置为 `false`
- `CONTRACT_STORAGE_ROOT`: 合同根目录，例如 `/volume1/contracts`

## Synology 侧准备

1. 在 NAS 创建共享文件夹（示例：`contracts`）。
2. 在共享文件夹下预建部门子目录（示例：`法务部`、`采购部`）。
3. 使用 DSM 对这些子目录分配部门用户权限。
4. 在容器中挂载该目录到 `CONTRACT_STORAGE_ROOT`。

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

访问前端：`http://NAS_IP:8080`

## 主要接口

- `POST /api/auth/login` 使用 Synology 用户名密码登录
- `GET /api/contracts` 查询合同（支持 department/status）
- `POST /api/contracts` 新建合同
- `PUT /api/contracts/:id` 更新合同
- `POST /api/contracts/:id/upload` 上传合同文件到部门目录
- `GET /api/departments` 读取共享目录下的部门文件夹

## 说明

系统不保存用户密码，不创建本地用户体系；仅在登录时调用 DSM 认证接口校验账号。
