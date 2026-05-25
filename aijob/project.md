# 项目固定信息

更新时间：2026-05-25

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
  - `backend/app/contracts.py`：合同蓝图入口（轻量）
  - `backend/app/contracts_routes_settings.py`：合同设置相关路由
  - `backend/app/contracts_routes_contracts.py`：合同主业务路由
  - `backend/app/contracts_routes_contracts_helpers.py`：仅合同路由使用的导入与建模辅助
  - `backend/app/contracts_core.py`：跨模块共享核心函数/常量（共享中心）
  - `backend/app/contracts_core_ai.py`：AI 解析与候选匹配辅助
  - `backend/app/files.py`：文件/文件夹管理接口（`/api/folders/*`）
  - `backend/app/files_core_helpers.py`：仅文件路由使用的目录/文件操作辅助
  - `backend/app/ocr_utils.py`：OCR 相关能力聚合模块（PDF提取、OCR回退、MinerU）
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
- `MINERU_API_KEY`：MinerU OCR 接口密钥
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
- 用户权限表：`users`
- 用户权限附加字段：`users.folders`（逗号拼接存储，前端多选回显为 `folder_list`）
- 默认保底部门：`财务部`
- 金额字段：`amount NUMERIC(20, 8)`
- 全文字段：`fullbody TEXT`
- 列表接口默认不返回 `fullbody`
- 详情接口 `/api/contracts/<id>` 返回含 `fullbody` 的详情

## 合同字段关键约定
- 必填字段：
  - `contract_name`
  - `handling_department`
- 可选字段（新增）：
  - `copy_count`：份数，纯数字整数，可为空
  - `save_place`：存档位置，文本，最大 50 字符，可为空
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
- `POST /api/folders/batch-match`：批量匹配当前文件夹下未关联合同的文件；先按路径中的部门与年份范围预筛候选，命中文件名合同编号时优先直连，否则再按中文关键名称匹配
- `GET /api/folders/file-count`：返回当前目录及子目录文件总数
- `PUT /api/folders/file/move`：将文件移动到目标目录，并同步更新已关联合同的 `file_path`
- `GET /api/settings/users`：读取用户权限列表；触发群晖 `docscool` 组同步、返回部门候选与同步提示
- `POST /api/settings/users`：新增用户权限记录（登录名需存在于群晖）
- `PUT /api/settings/users/<id>`：更新用户权限级别、部门范围、文件夹范围
- `DELETE /api/settings/users/<id>`：删除用户权限记录；删除后触发 `docscool` 组补齐型同步

## 本轮权限管理补充（2026-05-20）
- 设置页群晖调用已迁移为 `synology-api` SDK（`contracts_routes_settings.py`）。
- 用户权限新增“文件夹”字段：
  - 后端 `GET /api/settings/users` 新增 `folder_options` 返回。
  - 前端用户权限页新增“文件夹”多选列，并保存到 `users.folders`。
  - 文件夹候选当前规则：仅存储根目录下一级目录，首项“全部”。

## 本轮结构调整（2026-04-22）
- `folders` 相关接口已从 `contracts.py` 拆分到 `files.py`，应用通过 `files_bp` 蓝图注册。
- 对外 API 路径保持不变，前端无需调整路由地址。

## 本轮结构调整（2026-05-05）
- OCR 相关函数已从 `contracts.py` 迁移到 `ocr_utils.py`，并由 `contracts.py` 导入调用。
- 模块化后接口行为保持不变，主要目标为降低 `contracts.py` 复杂度与维护成本。

## 本轮结构调整（2026-05-11）
- 路由与核心进一步按“引用方内聚 + 共享中心”重构：
  - `contracts_routes_contracts_helpers.py` 承接合同路由私有辅助函数。
  - `files_core_helpers.py` 承接文件路由私有辅助函数。
  - `contracts_core.py` 保持跨模块共享能力，避免继续膨胀。
- 修复重构后的遗漏导入问题：
  - 合同保存链路补齐 `_normalize_contract_type_value` 导入。
  - 合同更新链路补齐 `_department_dir` 导入。

## 本轮稳定性补充（2026-05-12）
- `POST /api/contracts/ai-parse`：
  - 修复 AI 模块中超时常量缺失导入，消除 `EXTERNAL_API_TIMEOUT_SECONDS is not defined` 运行时错误。
- `POST /api/contracts/quick-match-files`：
  - 凭据过期场景统一返回 401，不再误报 500。
  - 修复 `_select_best_pdf_match` 的部门字段拼写错误与精确匹配分支返回结构错误，避免 `best_match['similarity']` 崩溃。
- 前端凭据过期联动：
  - 快速匹配“开始”执行时遇到 401/凭据过期文案，前端会自动清理登录态并跳转登录页。

## 本轮批量匹配增强（2026-05-14）
- `POST /api/folders/batch-match`：
  - 处理范围限定为当前文件夹，不递归子文件夹。
  - 候选合同按当前目录路径解析出的部门与年份范围联合过滤。
  - 文件名包含明确合同编号时优先按 `contract_number` 精确匹配。
  - 未命中合同编号时，继续沿用文件名中文关键名称匹配逻辑。

## 前端关键页面
- `frontend/src/views/LoginView.vue`：DSM 登录页
- `frontend/src/views/HomeView.vue`：首页汇总
- `frontend/src/views/ContractView.vue`：合同列表、创建、编辑、AI 上传、EXCEL 导入、PDF 预览、正文查看
- `frontend/src/views/FolderView.vue`：目录树、目录文件列表、文件合同关联、批量匹配
- `frontend/src/views/UserPermissionSettingsView.vue`：用户权限设置页（群晖 `docscool` 组映射）
- `frontend/src/components/ContractItem.vue`：合同新建/编辑/预览复用组件
- `frontend/src/components/AiMatchDialog.vue`：AI 识别结果确认复用组件

## 当前前端交互约定
- 合同名称列点击进入编辑，不再依赖整行点击
- 合同编号列强制单行显示，超长省略并支持悬浮查看
- AI 上传后先进入“识别结果确认”窗口，不直接进编辑框
- AI 上传触发“识别结果确认”窗口时，弹窗先显示“加载中...”，候选数据就绪后再渲染列表
- 点击合同名称打开编辑时，编辑弹窗先显示“加载中...”，详情和预览就绪后再显示表单
- 合同列表页“附件状态”筛选改为三态下拉：`全部 / 无附件 / 有附件`
- 合同列表页“按承办部门筛选”会额外合并当前数据里出现但部门表没有的值
- 编辑/新建弹窗里的部门下拉仍只使用部门配置表，不合并合同数据里的临时部门值
- 首页 `HomeView` 采用“前端缓存优先”加载策略：
  - 先读本地缓存 `docscool.home.dashboard`（TTL 5 分钟）作为默认展示
  - 同时请求后端统计与图表，返回后覆盖并回写缓存
  - 仅在“无缓存且后端仍加载中”时显示整页 `正在加载中...`
- 编辑/新建弹窗预览区右上角固定有：
  - `文本` 按钮
  - `上传文件` 按钮（先选树形目录，再选本地文件）
- 新建合同“上传文件”后会直接上传到选中目录并回填 `file_path`，保存合同时不再二次自动上传
- “文本”弹窗内容直接绑定 `form.fullbody`
- 导入弹窗底部保留：`下载模板` 链接样式按钮、`取消` 按钮、`选择文件` 按钮
- 主导航“系统设置”中不再显示“密码修改”和“退出”；右上角用户菜单暂时保留这两个入口
- 主导航“系统设置”已新增“用户权限”，桌面端和移动端菜单保持一致

## 本轮权限管理新增约定（2026-05-15）
- 用户权限映射：
  - `super_admin`：超管
  - `edit`：编辑
  - `view`：查看
- 部门范围字段：
  - 前端使用多选；后端按逗号拼接存储到 `users.departments`
  - 候选来源为“部门设置表 + 合同表历史部门”的去重并集
- 群晖组同步规则：
  - 页面读取时保证数据库用户与群晖 `docscool` 组双向一致（按数据库为基准）
  - 当前登录用户首次访问会自动补录到数据库
  - 当前登录用户属于 `administrators` 时，自动赋予超管和“全部”部门范围

## 本轮权限管理调整（2026-05-18）
- 用户列表读取前的同步已改为“只补齐不清理”：
  - 仅把数据库 `users` 表中缺失于 `docscool` 组的用户补入群组。
  - 不再自动补录当前登录用户。
  - 不再根据群晖用户详情回写数据库描述。
  - 不再把群组中数据库不存在的用户移除。
- `_synology_get_user_info` 仅作为“用户是否存在 + 描述”来源，并保留调试日志用于后续优化调用路径。

## 本轮权限管理调整（2026-05-25）
- 增删权限规则扩展为：仅 `super_admin` 或登录名 `zhangyan` 可执行“新增/删除”操作。
- 后端写接口守卫已覆盖：
  - `POST /api/settings/departments`
  - `DELETE /api/settings/departments/<id>`
  - `POST /api/settings/projects`
  - `DELETE /api/settings/projects/<id>`
  - `POST /api/settings/users`
  - `POST /api/settings/users/create-user`
  - `DELETE /api/settings/users/<id>`
  - `POST /api/settings/users/<id>/remove`
- 前端权限页联动：
  - `DepartmentSettingsView`、`ProjectSettingsView`、`UserPermissionSettingsView` 已按上述规则控制新增/删除按钮显隐。
  - 非授权用户进入相关页面时保持“可查看”，但新增/删除操作不可用。

### LoginView 视觉约定（2026-04-27）
- 登录右侧面板 `.login-panel`：
  - `padding: 50px 30px`
  - `border-radius: 25px`
  - `background: rgba(0, 0, 0, 0.08)`
  - `backdrop-filter: blur(1px)` 与 `-webkit-backdrop-filter: blur(1px)`

### FolderView 文件关联工作台交互
- 文件列表中存在真实匹配合同时，合同名称可点击并直接打开编辑弹窗
- 文件列表中 `<无匹配>` 行提供：`新建` 与 `AI` 两个快捷入口
- 文件列表标题栏提供：`上传文件`（多选上传到当前目录）和 `批量匹配`
- `批量匹配` 提示文案会明确展示：仅匹配当前文件夹、先按部门/年份范围缩小候选、命中文件名合同编号时优先直连
- 文件名右键菜单支持：`移动 / 改名 / 删除`
- 点击 `移动` 后弹出目录树选择框，确认后将文件移动到选定目录（支持根目录 `/`）
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
  - `AI识别`：点击后先提示“AI识别结果只会自动填写空白的字段”并停留约 5 秒；在有预览文件（已上传或已链接 PDF）时可点击，前端仅提交 `file_path` 到 `/contracts/ai-parse` 进行识别，仅对空白字段做补全，不覆盖用户已经手工填写的合同字段
  - `文本`：打开正文弹窗，直接编辑和查看 `form.fullbody`
  - `上传文件`：上传或选择本地合同文件
  - `链接文件`：从 NAS 目录选择并绑定已有 PDF 合同文件
- “AI上传”入口仍保留在合同列表页顶部工具栏，用于通过上传新 PDF 识别并进入候选匹配流程；“AI识别”则是在编辑/新建弹窗内，基于当前预览文件对表单做就地补全
- 全屏预览约定：文档尚未准备好时显示“预览加载中...”，仅在无可用文件时显示“暂无可预览内容”

### ContractView 视觉样式补充（2026-05-06）
- 顶部操作按钮组采用轻玻璃 + 阴影的 Apple 风格样式。
- 首个与最后一个按钮使用圆角，按钮间使用细分隔线。
- `el-scrollbar` 补丁样式必须限制在合同页作用域，禁止全局覆盖，避免污染下拉弹层高度。

## AI 相关固定约定
- AI 解析返回内容至少包括：
  - `fields`
  - `fullbody`
  - `match_candidates`
- `POST /api/contracts/ai-parse` 支持两种入口：
  - 上传 PDF 文件：后端先做直接文本提取，必要时再 OCR
  - 直接传 `fullbody`：当文本长度超过 20 时直接走 AI 结构化，不再 OCR
- 当前前端入口约定：优先走 `file_path` 提交，不再在前端做 `fullbody` 分支判断
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
