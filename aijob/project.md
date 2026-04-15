# 项目固定信息

更新时间：2026-04-14

## 项目定位
- 项目名称：DocsCool Contract Manager
- 目标：适配 Synology NAS 的前后端分离合同管理系统
- 核心能力：DSM 登录、合同结构化管理、PDF 预览、AI OCR/结构化提取、文件上传下载、EXCEL 导入

## 技术架构
- 后端：Flask + Flask-SQLAlchemy
- 数据库：SQLite
- 前端：Vue 3 + Vite + Element Plus + Axios
- PDF 预览：vue-pdf-embed + pdfjs-dist
- OCR / AI：PyMuPDF、RapidOCR、Pillow、numpy、MiniMax API
- NAS 集成：Synology DSM / FileStation API

## 目录约定
- backend：Flask API、模型、SQLite、NAS 上传下载、AI 解析
- frontend：Vue 页面、API 请求、预览和编辑交互
- docs：部署文档
- aijob：AI 辅助文档，包括长期记忆、项目固定参数、待办事项

## 本地开发固定参数
- 后端入口：`backend/run.py`
- 后端开发端口：`6000`
- 后端本地兼容虚拟环境：`backend/.venv312`
- 前端开发端口：`5173`
- 前端本地访问地址：`http://127.0.0.1:5173/docs/`
- 后端本地健康检查：`http://127.0.0.1:6000/api/health`
- 前端开发代理：`/api -> http://127.0.0.1:6000`

## 部署固定参数
- 默认部署模式：前后端分离，适配 Synology DSM 7.x + Container Manager
- Docker 入口文件：`docker-compose.yml`
- 默认 NAS 前端端口：`8080`
- README 中默认 NAS 后端端口映射示例：`5000`
- 本地开发已改为后端 `6000`，不要再按旧的 `5000` 做本地代理

## 后端关键环境变量
- `FLASK_ENV`：运行环境
- `APP_SECRET_KEY`：应用密钥
- `DATABASE_URL`：SQLite 地址，默认 `sqlite:///instance/contracts.db`
- `SYNOLOGY_BASE_URL`：DSM 地址，例如 `https://NAS_URL:5001`
- `SYNOLOGY_VERIFY_SSL`：是否校验证书，内网常设为 `false`
- `CONTRACT_STORAGE_MODE`：`local` 或 `remote`
- `CONTRACT_STORAGE_ROOT`：合同根目录，例如 `/volume1/contracts`
- `SYNOLOGY_FILESTATION_ROOT`：FileStation 视角路径，例如 `/contracts`
- `SYNOLOGY_UPLOAD_ACCOUNT`：远程上传使用的 DSM 账号
- `SYNOLOGY_UPLOAD_PASSWORD`：远程上传使用的 DSM 密码
- `SYNOLOGY_UPLOAD_SESSION`：默认 `FileStation`
- `MINIMAX_API_KEY`：AI 接口密钥
- `MINIMAX_API_URL`：默认 `https://api.minimaxi.com/v1/chat/completions`
- `MINIMAX_MODEL`：默认 `MiniMax-M2.5`
- `MY_COMP`：我方公司名称，用于 AI 提取时排除误识别为对方单位

## 存储模式约定
- `remote`：通过 FileStation API 直接上传到 NAS，共享目录权限由 DSM 控制
- `local`：后端直接写挂载目录
- 当前 README 默认推荐 `remote` 模式

## 数据模型关键约定
- 合同主表：`contracts`
- 部门表：`departments`
- 默认保底部门：`财务部`
- 金额字段：`amount NUMERIC(20, 8)`
- 全文字段：`fullbody TEXT`
- 列表接口默认不返回 `fullbody`
- 详情接口 `/api/contracts/<id>` 返回含 `fullbody` 的详情

## 合同字段关键约定
- 必填字段：
  - `contract_name`
  - `handling_department`
- 正文字段：`fullbody`


## 当前重要接口
- `GET /api/health`：健康检查
- `GET /api/contracts`：合同列表
- `GET /api/contracts/<id>`：合同详情，返回 `fullbody`
- `POST /api/contracts`：新建合同
- `PUT /api/contracts/<id>`：更新合同
- `POST /api/contracts/<id>/upload`：上传合同文件
- `GET /api/contracts/<id>/preview`：预览合同 PDF
- `GET /api/contracts/<id>/download`：下载原文件
- `POST /api/contracts/ai-parse`：AI OCR / 字段提取 / 返回 `fullbody`
- `POST /api/contracts/import-excel`：EXCEL 导入
- `GET /api/contracts/import-template`：下载导入模板
- `GET /api/contracts/import-error-report/<token>`：下载导入失败明细

## 前端关键页面
- `frontend/src/views/LoginView.vue`：DSM 登录页
- `frontend/src/views/HomeView.vue`：首页汇总
- `frontend/src/views/ContractView.vue`：合同列表、创建、编辑、AI 上传、EXCEL 导入、PDF 预览、正文查看

## 当前前端交互约定
- 合同名称列点击进入编辑，不再依赖整行点击
- 合同编号列强制单行显示，超长省略并支持悬浮查看
- AI 上传后先进入“识别结果确认”窗口，不直接进编辑框
- 编辑/新建弹窗预览区右上角固定有：
  - `文本` 按钮
  - `上传文件` 按钮
- 新建合同未保存前选择文件，会先进入待上传状态，保存合同后再自动上传
- “文本”弹窗内容直接绑定 `form.fullbody`
- 导入弹窗底部保留：`下载模板` 链接样式按钮、`取消` 按钮、`选择文件` 按钮

### 合同编辑/新建弹窗中的文件预览与 AI
- 编辑/新建弹窗左侧为“文件预览”区域：
  - 支持已上传合同 PDF 的预览和全屏查看
  - 支持从 NAS 目录中“链接文件”并即时在左侧预览
- 预览区域上方按钮现包含：
  - `AI识别`：在有预览文件（已上传或已链接 PDF，或本次待上传 PDF）时可点击，将当前文件提交到 `/contracts/ai-parse` 进行识别，仅对空白字段做补全，不覆盖用户已经手工填写的合同字段
  - `文本`：打开正文弹窗，直接编辑和查看 `form.fullbody`
  - `上传文件`：上传或选择本地合同文件
  - `链接文件`：从 NAS 目录选择并绑定已有 PDF 合同文件
- “AI上传”入口仍保留在合同列表页顶部工具栏，用于通过上传新 PDF 识别并进入候选匹配流程；“AI识别”则是在编辑/新建弹窗内，基于当前预览文件对表单做就地补全

## AI 相关固定约定
- AI 解析返回内容至少包括：
  - `fields`
  - `fullbody`
  - `match_candidates`
- AI 候选匹配排序：
  - 先金额相同
  - 再标题相似度降序
  - 标题相似最多补前 5 个
- 候选列表展示“匹配依据”
- 候选窗口左侧展示上传文件预览

## 后续文档维护规则
- 新增固定端口、环境变量、表结构、核心接口时，优先更新本文件
- 纯开发过程、一次性排查记录写入 `memory.md`
- 未来待办和方向性事项写入 `todo.md`
