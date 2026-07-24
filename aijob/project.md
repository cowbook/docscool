# 项目固定信息

## 项目定位
- 项目名称：DocsCool Contract Manager
- 目标：适配 Synology NAS 的前后端分离合同管理系统
- 核心能力：DSM 登录、合同结构化管理、PDF 预览、AI OCR/结构化提取、文件上传下载、EXCEL 导入

## 技术架构
- 后端：Flask + Flask-SQLAlchemy
- 数据库：MySQL（生产/当前运行）+ SQLite（历史源库/迁移来源）
- 前端：Vue 3 + Vite + Element Plus + Axios
- PDF 预览：vue-pdf-embed + pdfjs-dist
- OCR / AI：PyMuPDF、RapidOCR、Pillow、numpy、MiniMax API、讯飞 OCR
- NAS 集成：Synology DSM / FileStation API

## 代码模块与目录约定
- backend：Flask API、模型、SQLite、NAS 上传下载、AI 解析
  - backend/app/contracts.py：合同蓝图入口（轻量）
  - backend/app/contracts_routes_settings.py：合同设置相关路由
  - backend/app/contracts_routes_contracts.py：合同主业务路由
  - backend/app/contracts_routes_contracts_helpers.py：合同路由私有辅助
  - backend/app/contracts_core.py：跨模块共享核心函数/常量
  - backend/app/contracts_core_ai.py：AI 解析与候选匹配辅助
  - backend/app/files.py：文件/文件夹管理接口（/api/folders/*）
  - backend/app/files_core_helpers.py：文件路由私有目录/文件辅助
  - backend/app/ocr_utils.py：OCR 能力聚合模块
- frontend：Vue 页面、API 请求、预览和编辑交互
- docs：部署文档
- aijob：项目固定参数、长期记忆、待办

## 本地开发固定参数
- 后端入口：backend/run.py
- 后端开发端口：6000
- 后端本地兼容虚拟环境：backend/.venv312
- 前端开发端口：5173
- 前端本地访问地址：http://127.0.0.1:5173/docs/
- 后端本地健康检查：http://127.0.0.1:6000/api/health
- 前端开发代理：/api -> http://127.0.0.1:6000

## 部署与存储模式
- 默认部署模式：前后端分离（非 Docker）
- 存储模式：
  - remote：通过 FileStation API 上传到 NAS，共享目录权限由 DSM 控制
  - local：后端直接写挂载目录
- 推荐模式：remote
- 远程存储访问约定：
  - `SYNOLOGY_FILESTATION_ROOT` 与 `SYNOLOGY_FILESTATION_SCAN` 的读写均使用服务账号 `SYNOLOGY_USER` / `SYNOLOGY_PASSWORD`
  - DSM 用户登录、JWT、系统内权限判断仍使用真实登录用户，不改变现有认证流程

## 后端环境变量
- FLASK_ENV：运行环境
- APP_SECRET_KEY：应用密钥
- DATABASE_URL：当前运行数据库连接串（现为 MySQL）
- MYSQL_DATABASE_URL：MySQL 目标连接串（导入脚本优先读取）
- SOURCE_SQLITE_URL：SQLite 源库连接串（导入脚本读取）
- SYNOLOGY_BASE_URL：DSM 地址，例如 https://NAS_URL:5001
- SYNOLOGY_VERIFY_SSL：是否校验证书，内网常设为 false
- SYNOLOGY_USER：远程存储访问使用的服务账号
- SYNOLOGY_PASSWORD：远程存储访问使用的服务账号密码
- CONTRACT_STORAGE_MODE：local 或 remote
- CONTRACT_STORAGE_ROOT：合同根目录，例如 /volume1/contracts
- SYNOLOGY_FILESTATION_ROOT：FileStation 视角路径，例如 /contracts
- SYNOLOGY_FILESTATION_SCAN：扫描文件目录，例如 /contracts-scan
- MINIMAX_API_KEY：AI 接口密钥
- MINIMAX_API_URL：默认 https://api.minimaxi.com/v1/chat/completions
- MINIMAX_MODEL：默认 MiniMax-M2.5
- MINERU_API_KEY：MinerU OCR 接口密钥
- XUNFEI_APP_ID：讯飞 OCR 应用 ID
- XUNFEI_API_KEY：讯飞 OCR API Key
- XUNFEI_API_SECRET：讯飞 OCR API Secret
- XUNFEI_API_URL：默认 https://api.xf-yun.com/v1/private/hh_ocr_recognize_doc
- MY_COMP：我方公司名称，用于 AI 提取时排除误识别为对方单位

## MIS 合同详情 API 固定信息
- 用途：按合同号（htno）查询 MIS 合同主数据与付款明细
- 请求方式：GET
- 查询参数：
  - htno：合同号字符串（优先使用合同编号格式，即 `HTSP_ID`，例如 `CG-GK-B-2025-122`）
- 鉴权方式：HTTP Basic Auth
- 环境变量：
  - HT_DETAIL_API_URL：MIS 接口地址
  - HT_DETAIL_API_USERNAME：Basic Auth 用户名
  - HT_DETAIL_API_PASSWORD：Basic Auth 密码
- 响应结构（关键字段）：
  - HTSP_NO：合同编号
  - HTSP_ID：合同 ID
  - HTSP_NAM：合同名称
  - HYVEN_NO：供应商编号
  - WZHT_AMT：合同金额
  - HTSP_STA：合同状态
  - CBUSR_ID：经办人
  - CBCST_NO：成本中心
  - QDRQ_DTM：签订日期时间
  - payment：付款记录数组
- 调用约束：
  - 请求超时建议 20 秒
  - 响应可能为空对象或仅返回 `{"payment":[{}]}`，调用方需容错
  - payment 可能缺失或非数组，计数逻辑需做类型判断
  - 非 JSON 响应需记录错误摘要并继续后续批量处理
  - 不要求 `htno` 必须是纯数字；字母-数字组合合同号可直接查询

## 数据模型约定
- 关键表：contracts、departments、users
- users.folders：逗号拼接存储，前端回显为 folder_list
- 默认保底部门：财务部
- amount 字段：NUMERIC(20, 8)
- fullbody 字段：TEXT
- 列表接口默认不返回 fullbody
- 详情接口 /api/contracts/<id> 返回 fullbody

## 合同字段约定
- 必填字段：
  - contract_name
  - handling_department
- 可选字段：
  - copy_count：份数，纯数字整数，可为空
  - save_place：存档位置，文本，最大 50 字符，可为空
  - contract_form：合同形式，选项为 新签合同/补充合同/补充协议/变更合同
  - original_contract_id：原合同关联 ID（指向 contracts.id，可为空）
- 正文字段：fullbody

## 核心 API 清单
- GET /api/health：健康检查
- GET /api/contracts：合同列表
- GET /api/contracts/statistics：首页统计卡片数据
- GET /api/contracts/dashboard-charts：首页图表数据
- GET /api/contracts/<id>：合同详情（含 fullbody）
- POST /api/contracts：新建合同
- PUT /api/contracts/<id>：更新合同
- POST /api/contracts/<id>/upload：上传合同文件
- GET /api/contracts/<id>/preview：预览合同 PDF
- GET /api/contracts/<id>/download：下载原文件
- POST /api/contracts/ai-parse：AI OCR / 字段提取 / fullbody 返回
- GET /api/contracts/export-excel：按当前筛选条件导出合同信息 EXCEL（单工作表）
- POST /api/contracts/import-excel：EXCEL 导入
- GET /api/contracts/import-template：下载导入模板
- GET /api/contracts/import-error-report/<token>：下载导入失败明细
- PUT /api/html/<path>/full.md：保存 OCR Markdown，并按路径匹配合同同步更新 fullbody
- POST /api/webhook：执行 git pull，并异步触发前端重编译与后端重启（DSM/Linux 兼容）
- POST /api/folders/upload：向当前目录批量上传文件
- POST /api/folders/batch-match：批量匹配当前文件夹未关联合同文件
- GET /api/folders/file-count：返回当前目录及子目录文件总数
- GET /api/folders/scan-files：返回扫描目录中的最新 PDF 文件与缩略图信息
- POST /api/folders/scan-import：把扫描目录中的单个 PDF 导入到合同存储目录
- PUT /api/folders/file/move：移动文件并同步已关联合同 file_path
- GET /api/settings/users：读取用户权限列表
- POST /api/settings/users：新增用户权限
- PUT /api/settings/users/<id>：更新用户权限
- DELETE /api/settings/users/<id>：删除用户权限

## AI 与 OCR 约定
- /api/contracts/ai-parse 返回至少包含：fields、fullbody、match_candidates
- ai-parse 支持两种入口：
  - 上传 PDF：先做文本提取，必要时 OCR
  - 直接传 fullbody：文本长度超过 20 时直接结构化
- 当前前端入口优先提交 file_path
- OCR 回退链路：PDF 原生提取 -> 讯飞 OCR -> RapidOCR
- 候选匹配排序：先金额相同，再标题相似度降序，最多补前 5 个

## 目录批量匹配约定
- 入口：POST /api/folders/batch-match
- 作用范围：仅当前目录且仅未关联合同文件
- 目录预筛：按路径中的部门与年份范围过滤候选
- 文件名优先：命中合同编号时优先按 contract_number 精确匹配
- 关键名称规则：取文件名中第一个中文字符到最后一个中文字符之间的文本
- 候选范围：未归档 且 file_path 为空
- 匹配优先级：exact -> contains-single -> contains-best
- 单次匹配同一合同最多分配给一个文件

## 用户权限与同步约定
- 角色映射：
  - super_admin：超管
  - synology_super_admin：群晖超管（按超管权限处理）
  - edit：编辑
  - view：查看
- 部门范围：前端多选，后端存 users.departments 逗号串
- 文件夹范围：前端多选，后端存 users.folders 逗号串
- 群晖组同步策略：只补齐不清理（以数据库为准补入 docscool 组）
- 群晖管理员标识：接口可返回 is_synology_admin 供前端展示
- 增删权限守卫：仅 super_admin 或登录名 zhangyan 可执行新增/删除

## 前端页面与交互约定
- 页面职责：
  - frontend/src/views/LoginView.vue：DSM 登录
  - frontend/src/views/HomeView.vue：首页汇总
  - frontend/src/views/ContractView.vue：合同列表、创建编辑、AI 上传、导入与预览
  - frontend/src/views/ContractScanView.vue：扫描目录 PDF 工作台，左侧缩略图、右侧预览、导入合同
  - frontend/src/views/FolderView.vue：目录与文件关联工作台
  - frontend/src/views/UserPermissionSettingsView.vue：用户权限设置
- 合同列表与编辑：
  - 合同名称列点击进入编辑
  - 合同编号列单行省略并支持悬浮
  - 合同列表可显示“原合同”关联信息（合同编号 + 名称）
  - 编辑/新建弹窗支持 文本、上传文件、链接文件、AI识别
  - AI识别仅补全空白字段，不覆盖手填字段
- 首页加载：
  - 先读本地缓存 docscool.home.dashboard（TTL 5 分钟）
  - 再请求后端并覆盖回写
  - 右侧独立显示两个文档区：`扫描仪` 与 `最新上传`
  - `扫描仪` 区域展示扫描目录里的最新 PDF，单行横向滚动
  - 点击首页 `扫描仪` 缩略图后跳转到 `ContractScanView` 并自动选中该文件
- 文件工作台：
  - 支持上传、批量匹配、移动、改名、删除
  - 支持快捷新建与 AI 入口
  - 文件总数通过 /api/folders/file-count 单请求返回
- 预览体验：
  - 预览准备阶段显示加载态
  - 无可预览内容时显示空态

## 文档维护规则
- 本文件只保留长期稳定的固定信息（架构、约定、接口、字段、环境变量）
- 一次性排查过程与临时记录写入 aijob/memory.md
- 待办与计划写入 aijob/todo.md
