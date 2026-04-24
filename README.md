# DocsCool Contract Manager

前后端分离合同管理系统，适配 Synology NAS：
- 文件存储在共享目录，按部门子目录落盘，复用 NAS 权限管理。
- 登录直接校验 Synology DSM 账号密码，不维护本地用户表。
- 结构化合同数据存储在 SQLite。
- 支持 PDF 预览、AI OCR/解析、远程 FileStation 上传下载。

## 目录结构

- `backend`: Flask API + SQLite
- `frontend`: Vue3 + Element Plus

## 后端环境变量

编辑 `backend/.env`：

- `SYNOLOGY_BASE_URL`: DSM 地址，例如 `https://192.168.1.10:5001`
- `SYNOLOGY_VERIFY_SSL`: 内网自签名证书通常设置为 `false`
- `CONTRACT_STORAGE_MODE`: `local` 或 `remote`
- `CONTRACT_STORAGE_ROOT`: 合同根目录，例如 `/volume1/contracts`
- `SYNOLOGY_FILESTATION_ROOT`: 群晖 FileStation 中的共享目录路径，例如 `/contracts`
- `MINIMAX_API_KEY`: 启用 AI 识别时必填

推荐参考 [backend/.env.example](backend/.env.example) 完成配置。

## Synology 侧准备

1. 创建共享文件夹用于存放合同文件，例如 `contracts`。
2. 在该共享目录下预建部门子目录，例如 `法务部`、`采购部`、`工程部`。
3. 为实际使用系统的 DSM 用户分配这些目录的访问权限。
4. 为实际登录系统的 DSM 用户分配 FileStation 上传/下载权限。
5. 确认 DSM 的 HTTPS 地址可以从后端服务所在主机访问，例如 `https://NAS_IP:5001`。

## 部署方式选择

本项目支持两种 NAS 存储模式：

### 1. `remote` 模式

- 合同文件通过 FileStation API 直接上传到 NAS。
- 适合当前项目默认部署方式。
- 上传与下载均使用当前登录用户的 DSM 凭证。
- 需要配置：
	- `SYNOLOGY_BASE_URL`
	- `SYNOLOGY_FILESTATION_ROOT`

### 2. `local` 模式

- 后端服务直接写 `CONTRACT_STORAGE_ROOT` 指向的目录。
- 需要确保后端进程运行用户对该路径有读写权限。

## 首次部署后的检查项

1. 使用 DSM 账号登录系统，确认可以成功登录。
2. 新建一条合同并上传 PDF，确认上传成功。
3. 打开合同编辑框，确认 PDF 可以预览。
4. 测试合同下载，确认能从 NAS 正常取回文件。
5. 测试 AI 解析，确认接口密钥和超时时间配置正常。

## 常见问题

### 1. 前端能打开，但无法登录

优先检查：

- `SYNOLOGY_BASE_URL` 是否可从后端服务所在主机访问
- DSM 账号密码是否正确
- DSM 是否开启 5001 HTTPS 访问
- 自签名证书场景下 `SYNOLOGY_VERIFY_SSL` 是否为 `false`

### 2. 上传或预览失败

优先检查：

- `SYNOLOGY_FILESTATION_ROOT` 是否写对
- 当前登录 DSM 用户是否有共享目录权限
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

## 合同字段补充说明

- 必填字段：`contract_name`、`handling_department`
- 金额字段：`contract_amount` 可为空（留空表示未知或暂未录入）
- 新增可选字段：
	- `copy_count`：份数，纯数字整数，可为空
	- `save_place`：存档位置，文本，最大 50 字符，可为空

## EXCEL 导入模板补充

- 模板已包含“份数”“存档位置”列：
	- 份数：仅允许纯数字整数（可留空）
	- 存档位置：最多 50 字符（可留空）

## 说明

系统不保存用户密码，不创建本地用户体系；仅在登录时调用 DSM 认证接口校验账号。
