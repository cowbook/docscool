# 项目固定信息

更新时间：2026-04-22

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
- OCR / AI：PyMuPDF、RapidOCR、Pillow、numpy、MiniMax API、讯飞通用文字识别（intsig）
- NAS 集成：Synology DSM / FileStation API

## 目录约定
- backend：Flask API、模型、SQLite、NAS 上传下载、AI 解析
  - `backend/app/contracts.py`：合同主业务、AI 提取、导入等
  - `backend/app/files.py`：文件/文件夹管理接口（`/api/folders/*`）
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
- 默认部署模式：前后端分离（非 Docker）
- 后端服务端口：`6000`（本地开发默认）
- 前端服务端口：`5173`（本地开发默认）

## 后端关键环境变量
- `FLASK_ENV`：运行环境
- `APP_SECRET_KEY`：应用密钥
- `DATABASE_URL`：SQLite 地址，默认 `sqlite:///instance/contracts.db`
- `SYNOLOGY_BASE_URL`：DSM 地址，例如 `https://NAS_URL:5001`
- `SYNOLOGY_VERIFY_SSL`：是否校验证书，内网常设为 `false`
- `CONTRACT_STORAGE_MODE`：`local` 或 `remote`
- `CONTRACT_STORAGE_ROOT`：合同根目录，例如 `/volume1/contracts`
- `SYNOLOGY_FILESTATION_ROOT`：FileStation 视角路径，例如 `/contracts`
- `MINIMAX_API_KEY`：AI 接口密钥
- `MINIMAX_API_URL`：默认 `https://api.minimaxi.com/v1/chat/completions`
- `MINIMAX_MODEL`：默认 `MiniMax-M2.5`
- `XUNFEI_APP_ID`：讯飞 OCR 应用 ID
- `XUNFEI_API_KEY`：讯飞 OCR API Key
- `XUNFEI_API_SECRET`：讯飞 OCR API Secret
- `XUNFEI_API_URL`：默认 `https://api.xf-yun.com/v1/private/hh_ocr_recognize_doc`
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
- `GET /api/contracts/statistics`：首页统计卡片数据
- `GET /api/contracts/dashboard-charts`：首页图表数据
- `GET /api/contracts/<id>`：合同详情，返回 `fullbody`
- `POST /api/contracts`：新建合同
- `PUT /api/contracts/<id>`：更新合同
- `POST /api/contracts/<id>/upload`：上传合同文件
- `GET /api/contracts/<id>/preview`：预览合同 PDF
- `GET /api/contracts/<id>/download`：下载原文件
- `POST /api/contracts/ai-parse`：AI OCR / 字段提取 / 返回 `fullbody`，同时支持直接提交 `fullbody` 文本跳过 OCR
- `POST /api/contracts/import-excel`：EXCEL 导入
- `GET /api/contracts/import-template`：下载导入模板
- `GET /api/contracts/import-error-report/<token>`：下载导入失败明细
- `POST /api/folders/upload`：向当前目录批量上传文件
- `POST /api/folders/batch-match`：按文件名中文关键名称批量匹配合同（仅处理未关联合同的文件）
- `GET /api/folders/file-count`：返回当前目录及子目录文件总数

## 本轮结构调整（2026-04-22）
- `folders` 相关接口已从 `contracts.py` 拆分到 `files.py`，应用通过 `files_bp` 蓝图注册。
- 对外 API 路径保持不变，前端无需调整路由地址。

## 前端关键页面
- `frontend/src/views/LoginView.vue`：DSM 登录页
- `frontend/src/views/HomeView.vue`：首页汇总
- `frontend/src/views/ContractView.vue`：合同列表、创建、编辑、AI 上传、EXCEL 导入、PDF 预览、正文查看
- `frontend/src/views/FolderView.vue`：目录树、目录文件列表、文件合同关联、批量匹配
- `frontend/src/components/ContractItem.vue`：合同新建/编辑/预览复用组件
- `frontend/src/components/AiMatchDialog.vue`：AI 识别结果确认复用组件

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

### FolderView 文件关联工作台交互
- 文件列表中存在真实匹配合同时，合同名称可点击并直接打开编辑弹窗
- 文件列表中 `<无匹配>` 行提供：`新建` 与 `AI` 两个快捷入口
- 文件列表标题栏提供：`上传文件`（多选上传到当前目录）和 `批量匹配`
- 左右面板之间支持拖拽分隔，桌面端可调整目录树宽度
- 当 `ContractItem` 在 FolderView 中使用时隐藏“上传文件/链接文件”按钮，并新增“解绑合同”按钮
- “新建并带文件路径”时，弹窗进入即加载预览，不再提示“保存后再看”
- 文件数量统计：
  - 当前目录文件数使用前端 `currentFileCount`（来自当前 `files` 列表）
  - 目录总文件数（含子目录）改为单请求 `GET /api/folders/file-count`，不再前端递归多次请求

## 本轮稳定性补充
- 针对远程存储统计，后端递归计数逻辑已改为复用同一 Synology 会话。
- 统计过程中若会话失效（错误码 `119`），会自动重登并对当前节点重试一次。

### 合同编辑/新建弹窗中的文件预览与 AI
- 编辑/新建弹窗左侧为“文件预览”区域：
  - 支持已上传合同 PDF 的预览和全屏查看
  - 支持从 NAS 目录中“链接文件”并即时在左侧预览
- 预览区域上方按钮现包含：
  - `AI识别`：点击后先提示“AI识别结果只会自动填写空白的字段”并停留约 5 秒；在有预览文件（已上传或已链接 PDF，或本次待上传 PDF）时可点击，将当前文件提交到 `/contracts/ai-parse` 进行识别，仅对空白字段做补全，不覆盖用户已经手工填写的合同字段；若 `form.fullbody` 已有超过 20 个字符，则直接提交 `fullbody` 给后端 AI 结构化，跳过 OCR
  - `文本`：打开正文弹窗，直接编辑和查看 `form.fullbody`
  - `上传文件`：上传或选择本地合同文件
  - `链接文件`：从 NAS 目录选择并绑定已有 PDF 合同文件
- “AI上传”入口仍保留在合同列表页顶部工具栏，用于通过上传新 PDF 识别并进入候选匹配流程；“AI识别”则是在编辑/新建弹窗内，基于当前预览文件对表单做就地补全

## AI 相关固定约定
- AI 解析返回内容至少包括：
  - `fields`
  - `fullbody`
  - `match_candidates`
- `POST /api/contracts/ai-parse` 支持两种入口：
  - 上传 PDF 文件：后端先做直接文本提取，必要时再 OCR
  - 直接传 `fullbody`：当文本长度超过 20 时直接走 AI 结构化，不再 OCR
- 上传 PDF 的 OCR 回退链路：
  - 先尝试 PDF 原生文本提取
  - 失败后优先尝试讯飞 OCR（PDF 转 PNG 后逐页识别）
  - 讯飞失败再回退 RapidOCR 本地识别
- AI 候选匹配排序：
  - 先金额相同
  - 再标题相似度降序
  - 标题相似最多补前 5 个
- 候选列表展示“匹配依据”
- 候选窗口左侧展示上传文件预览

## 目录批量匹配固定约定
- 入口：`POST /api/folders/batch-match`
- 作用范围：仅匹配当前目录下“没有关联合同”的文件；已有关联合同文件会跳过并记录
- 关键名称规则：取文件名中第一个中文字符到最后一个中文字符之间的文本
- 候选范围：仅 `未归档` 且 `file_path` 为空的合同
- 匹配优先级：
  - 合同名与关键名称完全相同（`exact`）
  - 否则若“包含关键名称”候选只有 1 个（`contains-single`）
  - 否则按相似度最高取第 1 个（`contains-best`）
- 单次匹配中同一合同仅会被分配给一个文件，避免重复占用

## 后续文档维护规则
- 新增固定端口、环境变量、表结构、核心接口时，优先更新本文件
- 纯开发过程、一次性排查记录写入 `memory.md`
- 未来待办和方向性事项写入 `todo.md`
