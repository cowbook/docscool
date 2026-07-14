# AI 工作记忆

更新时间：2026-06-10

## 使用约定
- 本文件用于记录 AI 已完成、已确认、待回归的重要工作，按时间顺序持续追加。
- 后续 AI 在继续开发前，优先阅读本文件，避免重复判断、重复改动和遗漏既有约定。
- 记录应以“已验证事实”为主，尽量避免写未经确认的猜测。

## 时间线

### 2026-07-14 本轮更新
- 扫描目录工作台落地：
	- 新增 `frontend/src/views/ContractScanView.vue` 与路由 `/contracts/scan`。
	- 页面左侧展示扫描目录 PDF 首页缩略图，右侧展示所选 PDF 预览。
	- 点击“导入合同”时，不再上传本地文件，而是先把扫描目录中的 PDF 复制到合同存储目录，再复用现有 `/api/contracts/ai-parse` 与候选匹配弹窗链路。
- 首页新增“扫描仪”区域：
	- `HomeView` 右侧新增独立区块，展示扫描目录中最新 PDF 文件。
	- 区域样式复用“最新上传”视觉，但布局为单行横向滚动。
	- 点击缩略图后跳转到 `ContractScanView`，并通过路由参数自动选中文件。
- 存储权限模型调整：
	- 远程模式下，`SYNOLOGY_FILESTATION_ROOT` 与 `SYNOLOGY_FILESTATION_SCAN` 的 FileStation 读写统一改用 `SYNOLOGY_USER` / `SYNOLOGY_PASSWORD`。
	- DSM 用户登录、JWT、用户/群组管理相关 Synology Core API 仍保留为真实登录用户链路。

### 2026-06-10 本轮更新
- 用户权限页（UserPermissionSettingsView）交互重构：
	- “创建用户”与“编辑用户”已合并为同一弹窗代码，编辑模式复用同一表单。
	- 编辑模式下“登录名”禁用不可修改，且不显示“密码/密码验证”输入框。
	- 原独立“编辑权限”弹窗已移除；表格“编辑”按钮改为打开共享弹窗。
- 权限绑定交互升级：
	- 创建/编辑弹窗中的“新增权限绑定”文案统一为“新增权限”，并显示线型加号图标。
	- 权限列在创建弹窗中改为下拉单选（编辑/查看）。
	- 创建弹窗尺寸调整：宽度提升到 `810px`，最小高度为 `90vh`，内容区可滚动。
- 群晖管理员视觉标识：
	- 后端 `GET /api/settings/users` 已附带 `is_synology_admin` 字段（基于 `administrators` 组成员）。
	- 前端用户列表中若 `is_synology_admin=true`，登录名图标显示金色，tooltip 追加“（群晖管理员）”。

### 2026-06-03 本轮更新
- 全屏预览弹窗标题新增存储目录面包路径（/ 分隔）：
	- `ContractItem` 中主预览全屏弹窗与右侧链接预览全屏弹窗，标题区改为“文件名 + 目录”。
	- `HomeView` 中“最新上传”全屏预览弹窗同步新增“目录：/a/b/c”显示。
- 目录显示规则：
	- 由 `file_path` 提取父目录路径。
	- 根目录或无父目录时显示 `/`。
	- 长路径在标题行省略展示，悬浮可查看完整路径。

### 2026-05-26 本轮更新
- OCR 预览入口统一：
	- 前端文件名点击改为新窗口打开目录式预览 URL：`/docs/preview/<encoded_dir>/`。
	- 合同列表页与文件夹页点击文件名不再触发本页弹层预览。
- OCR 元数据与 PDF 预览稳态增强：
	- `GET /api/html-meta/<path>` 在无 `_origin.pdf` 时回退到存储目录 PDF 预览地址。
	- 前端对受保护 PDF 链接先鉴权拉取 blob，再注入 iframe，消除 `Missing token` 与 404 闪现。
	- 左侧预览新增加载态：优先显示“加载中...”。
- OCR 编辑器升级与可用性修复：
	- `OcrPreviewView` 从简单文本框升级为 Toast UI 编辑器（WYSIWYG），保留图片上传。
	- 编辑器宿主从条件卸载改为 `v-show`，修复模式切换后编辑区空白。
	- 工具栏采用“独立 AI 按钮 + 编辑按钮组”结构；AI 按钮识别中展示小转圈动画。
- 无 `full.md` 场景接入 AI 补全流程：
	- 当 `markdown_exists=false` 时禁用“进入编辑”。
	- 新增 `AI识别/重新AI识别` 按钮调用 `POST /api/contracts/ai-parse`。
	- 识别成功后自动刷新 meta 与 markdown，检测到 `full.md` 后解锁编辑。
- 编辑态图片显示修复：
	- 相对路径资源在编辑器内临时改写为 `/api/html/...`，确保 WYSIWYG 中可见。
	- 从编辑器同步与保存时将 API 地址逆变换回相对路径，保持 markdown 内容干净。

### 2026-05-25 本轮更新
- 权限规则扩展：
	- 新增/删除能力由“仅超管”扩展为“仅超管或登录名 `zhangyan`”。
- 后端权限守卫落地：
	- `contracts_routes_settings.py` 中统一写接口守卫已按新规则放行。
	- 用户管理相关接口（新增用户、创建用户、删除用户、移除用户）已接入守卫。
	- 部门/项目新增删除接口继续复用同一守卫，规则保持一致。
- 前端页面联动：
	- `UserPermissionSettingsView` 已根据当前用户权限与登录名控制“添加用户/创建用户/移除/删除”入口。
	- `DepartmentSettingsView`、`ProjectSettingsView` 延续只读态策略，非授权用户仅查看。

### 2026-05-22 本轮更新
- 前端 `ai-parse` 调用统一：
	- `ContractView`、`FolderView`、`ContractItem` 均已改为提交 `file_path`。
	- `ContractItem.runAiRecognitionFromPreview` 已去除前端 `fullbody` 分支，仅提交 `file_path`。
- `ContractItem` 上传交互改造：
	- “上传文件”改为先弹树型目录选择框，再选择本地文件。
	- 目录确认后通过 `/api/folders/upload` 上传，返回 `file_path` 后回填到当前合同。
	- 编辑态会立即写回合同 `file_path`；新建态会先回填并提示“保存后生效”。
- 后端 MinerU 结果落盘规则调整：
	- `mineru_extract_text_from_uploaded_pdf` 支持接收来源 `file_path`。
	- OCR 结果不再按返回 UUID 落盘，改为 `instance/ocr/<相对目录>/<文件名去扩展名>/`。
	- 增加目录名清洗与路径安全检查（过滤非法字符、忽略 `.`/`..`）。

### 2026-05-20 本轮更新
- Synology SDK 路径验证与落地：
	- 新增 `backend/scripts/test_synology_admin_group_users_sdk.py`，使用 `synology-api` SDK 实测管理员组成员读取。
	- 已验证 `group.get_users(in_group=True)` 在当前环境可返回成员，并可识别 `zhangyan`。
- 设置页群晖调用改造：
	- `backend/app/contracts_routes_settings.py` 已切换为 `synology-api` SDK 进行用户/群组读取、建组、加组成员等操作。
	- 保留调用前后日志摘要，便于继续定位 DSM 行为差异。
- 用户权限新增“文件夹”字段（全链路）：
	- 数据库模型 `users` 新增 `folders` 字段，`to_dict()` 返回 `folders/folder_list`。
	- 设置页接口 `GET /api/settings/users` 返回 `folder_options`；`PUT /api/settings/users/<id>` 支持保存 `folders`。
	- 前端用户权限页新增“文件夹”多选列并接入保存。
- 文件夹选项规则最终确认：
	- 仅列出存储根目录下一级目录；不再枚举二级/三级目录。
	- 前端选项首项固定为“全部”。
- 运行观察：
	- 获取 `folder_options` 时偶发 FileStation `119` 会话失效，触发过一次 `/api/settings/users` 500（后续重试可恢复）。

### 2026-05-18 本轮更新
- 用户权限同步策略改为“单向补齐”：
	- `GET /api/settings/users` 前的同步逻辑已调整为：只检查数据库 `users` 表中的登录名。
	- 若数据库用户未在群晖 `docscool` 组中，则补充加入该组。
	- 取消其它自动同步行为：不再自动补录当前登录用户、不再按群晖回写描述、不再清理群组中数据库不存在的成员。
- 用户权限页新增删除能力：
	- 前端用户权限表“操作”列新增 `删除` 按钮，包含确认弹窗。
	- 后端新增 `DELETE /api/settings/users/<id>`，删除数据库 `users` 记录，并在删除后触发一次 `docscool` 组“补齐型”同步。
- 群晖用户查询调试增强：
	- `_synology_get_user_info` 已增加 GET/POST 调用前后摘要日志（请求参数、success、error code、users_count）。
	- 便于后续基于真实日志裁剪调用 attempt。
- 噪声日志抑制：
	- 应用启动中已全局忽略 `urllib3` 的 `InsecureRequestWarning`，减少 `verify=False` 场景下日志干扰。
- 代码清理：
	- `contracts_routes_settings.py` 已删除当前流程下不再使用的函数与字段，保留最小必需链路。
- 下次优化方向：
	- 专门测试能正确验证“用户名与用户组关系”的 Synology API，不再接受校验不可用直接放行。
	- 优先确认 `Group.Member.get_users`、`Group` 及相关成员接口在当前 DSM 上的真实返回与限制。

### 2026-05-15 本轮更新
- 系统设置新增“用户权限”菜单与页面：
	- `MainLayout` 的桌面导航与移动端抽屉导航均新增“系统设置 -> 用户权限”。
	- 新增 `UserPermissionSettingsView` 页面，含说明文案：`本系统管理的用户权限对应群晖里的docscool用户组`。
	- 页面顶部提供 Apple 风格“新建用户”按钮，下方用户列表字段为：`登录名称 / 描述 / 权限 / 部门`。
	- 权限支持 3 级单选：`超管 / 编辑 / 查看`；部门支持多选并按逗号文本存储。
- 后端新增用户权限数据模型与接口：
	- 新增数据库表模型 `users`（`UserPermission`）：记录登录名、描述、权限、部门与时间戳。
	- 新增 `GET /api/settings/users`：执行群晖用户组同步后返回数据库用户列表与部门候选。
	- 新增 `POST /api/settings/users`：按登录名新增用户权限记录（要求该用户存在于群晖）。
	- 新增 `PUT /api/settings/users/<id>`：更新权限级别与部门配置。
- 群晖 `docscool` 组同步链路落地：
	- 读取用户列表时，先检查当前登录用户是否在数据库；若不在则自动补录。
	- 若当前登录用户属于 `administrators` 组，则默认权限置为 `super_admin`，部门置为 `全部`。
	- 检查群晖 `docscool` 组是否存在，不存在则创建；并尝试赋予存储根目录编辑权限（失败仅 warning，不阻断流程）。
	- 检查数据库用户是否都在 `docscool` 组，不在则补加。
	- 检查 `docscool` 组成员是否都存在数据库，不在则从组中移除。
	- 同步返回的数据以数据库 `users` 表为准。

### 2026-05-14 本轮更新
- FolderView 批量匹配能力增强：
	- 前端弹窗说明已更新，明确“只处理当前文件夹，不含子文件夹”。
	- 候选合同不再全量扫描，改为先按当前文件夹路径中的“部门 + 年份范围”预筛选未归档且未绑文件的合同。
	- 若文件名中出现明确合同编号（字母/数字/连字符组合），后端优先按 `contract_number` 直连匹配，降低名称模糊匹配误绑概率。
	- 其余文件仍沿用“提取中文关键名称 -> 精确/包含/最相似匹配”的原有批量匹配链路。
- 批量匹配后端修正：
	- 修复本轮人工改动中在循环外提前使用 `file_path` 的运行时错误风险。
	- 修复部门筛选覆盖年份筛选的问题，当前为部门与年份范围共同收敛候选集。
	- 修复合同编号优先分支只返回单条结果并提前中断整批任务的问题，改为逐文件独立处理。

### 2026-05-13 本轮更新
- FolderView 文件右键菜单新增“移动”能力：
	- 前端新增“移动文件”弹窗，内置目录树选择目标目录，支持选择根目录 `/`。
	- 移动前校验“目标目录与当前目录一致”并给出提示，避免无意义请求。
	- 移动成功后刷新当前文件列表与目录统计，并同步当前预览行路径。
- 后端新增文件移动接口：
	- 新增 `PUT /api/folders/file/move`。
	- 本地模式使用 `os.rename` 完成移动，校验目标目录存在与同名冲突。
	- 远程模式使用 Synology `SYNO.FileStation.CopyMove`（`remove_src=true`）实现移动。
	- 成功后同步更新合同表中匹配 `file_path` 的记录，保持文件与合同绑定一致。

### 2026-05-12 本轮更新
- 合同列表导入交互修复：
	- `ContractView` 导入弹窗内“选择文件”按钮绑定 `importingExcel`。
	- 选择文件后立即显示“导入中...”，并进入不可用状态，导入结束后恢复。
- AI 解析链路修复：
	- 修复 `contracts_core_ai.py` 中 `EXTERNAL_API_TIMEOUT_SECONDS` 未导入导致的 `ai-parse` 500。
- 快速匹配链路连续修复：
	- 修复 `quick-match-files` 在“登录凭据已过期”场景误返回 500，改为 401。
	- 修复 `_select_best_pdf_match` 中 `handing_department` 拼写错误导致的属性异常。
	- 修复 `_select_best_pdf_match` 精确匹配分支返回结构错误导致 `best_match['similarity']` 崩溃。
	- 快速匹配前端已补齐凭据过期自动退出并跳转登录页逻辑。
- 运行日志观察：
	- 远程 NAS 场景存在大量 `InsecureRequestWarning`，来源为 `verify=False` 的 HTTPS 请求。
	- 该项当前属于告警噪声，未影响主流程结果；后续可考虑按配置开关抑制告警或启用证书校验。

### 2026-05-11 本轮更新
- 后端深拆策略调整并落地：
	- 不再仅按“大功能块”拆分，改为按“引用方内聚”拆分。
	- 新增 `backend/app/contracts_routes_contracts_helpers.py`，承接仅合同路由使用的导入/建模辅助函数。
	- 新增 `backend/app/files_core_helpers.py`，承接仅文件路由使用的目录与文件操作辅助函数。
	- `backend/app/contracts_core.py` 进一步降至约 953 行，保持共享能力中心定位。
- 合同保存/更新报错修复：
	- 修复 `backend/app/contracts_routes_contracts_helpers.py` 中 `_build_contract_record` 调用 `_normalize_contract_type_value` 但未导入导致的运行时错误。
	- 修复 `backend/app/contracts_routes_contracts.py` 中 `update_contract` 调用 `_department_dir` 但未导入导致的 `NameError`（PUT 500）。
- 验证结果：
	- `py_compile` 通过。
	- `create_app` 冒烟通过。
	- 合同创建接口与合同更新接口已完成带鉴权回归验证，修复后不再出现对应 500。

### 2026-05-09 本轮更新
- 合同列表筛选调整：
	- `has_file` 已从开关改为三态下拉：`全部 / 无附件 / 有附件`。
	- 后端 `GET /api/contracts` 已同时支持 `has_file=true` 与 `has_file=false`，其中 `false` 会筛选 `file_path` 为空的合同。
- 承办部门筛选增强：
	- 合同列表页的“按承办部门筛选”下拉，会把当前合同数据里出现但部门表中不存在的值也补进去。
	- 编辑/新建弹窗中的部门下拉保持原状，只使用部门配置表里的固定选项。
- 系统设置导航整理：
	- 主导航“系统设置”子项已移除“密码修改”和“退出”。
	- 右上角用户菜单暂时仍保留“密码修改”和“退出”。

### 2026-05-06 本轮更新
- AI 上传候选弹窗“先开窗后加载”体验优化：
	- `ContractView` 中 AI 上传后改为立即打开 `AiMatchDialog` 并进入 loading 状态。
	- 数据返回后再显示候选合同列表，避免等待期间无反馈。
	- `AiMatchDialog` 新增 `loading` 属性与加载态占位，加载中禁用“下一步”。
- 合同编辑弹窗“点击即开”体验优化：
	- `ContractItem` 中 `openEditWithSupplementalFields` 改为先打开编辑弹窗并显示“加载中...”。
	- 再异步请求合同详情与 PDF 预览，准备完成后显示完整表单。
	- 加载中禁用“保存/解绑”，失败时关闭弹窗并提示错误。
- 全屏预览加载状态修复：
	- 主预览全屏与链接文件全屏在文档未就绪时显示“预览加载中...”，不再误显示“暂无可预览内容”。
- 下拉菜单底部空白修复：
	- 定位到 `ContractView` 的全局 `.el-scrollbar { padding-bottom: 32px; }` 污染了所有 popper 下拉。
	- 已改为仅作用于合同页容器作用域，消除用户菜单与选择器下拉的额外底部空白。
- 合同页操作按钮组视觉升级：
	- 顶部 `el-button-group` 增加 Apple 风格轻玻璃与阴影。
	- 首个与最后一个按钮设置圆角，补充 hover/active 反馈。

### 2026-05-05 本轮更新
- OCR 模块化收敛：
	- 新增 `backend/app/ocr_utils.py`，集中承载 OCR 相关实现（PDF 文本提取、RapidOCR 回退、MinerU 提取等）。
	- `contracts.py` 中 OCR 相关函数已迁移为从 `ocr_utils.py` 导入调用，减少主业务文件体积。
	- 迁移过程中已处理循环依赖：`_preview_lines` 下沉到 `ocr_utils.py` 后复用。
- 登录态与异常处理：
	- 前端在请求 `/folders/children` 等目录接口遇到凭据过期提示时，已支持自动清 token 并跳转登录页。
- 导入模板下载修复：
	- 修复 `ContractView` 导入模板下载“后端 200 但前端报失败”问题。
	- 根因是页面缺失 `parseFilenameFromDisposition` / `triggerBrowserDownload`，补齐后下载恢复正常。
- 首页最新上传角标样式：
	- 右上角角标从方形改为直角三角形切角样式。
	- 角标底色已改为半透明渐变。

### 2026-04-29 本轮更新
- HomeView 首页响应式与右侧“最新上传”区域优化：
	- `latest-grid` 已从固定列 Grid 改为可换行 Flex，自适应一行展示数量。
	- 缩略图尺寸上限调整为 `168x232`（原 `210x290` 的 80%），避免窄屏挤压。
	- 缩略图增加悬停放大效果（hover/focus），并增加边框高亮、阴影与向上位移反馈。
	- 断点按常用宽度微调（1366/1024/768/390），中屏保持左窄右宽布局，避免左侧主区占满。
	- 右侧文件名改为 3 行截断省略，字号下调到 `clamp(11px, 0.78vw, 13px)`。
	- 首页“总金额/归档金额”改为“数字+单位”分段渲染，单位采用浅色 `14px`。
- 最新上传“修改人”来源改造（后端）：
	- `GET /api/folders/latest-uploads` 不再通过合同信息回查 `handler/created_by`。
	- 本地存储与远程存储均改为直接返回文件系统来源的 `modified_by`。
	- 远程模式下 Synology 列表 `additional` 增加 `owner` 信息用于用户名提取。

### 2026-04-27 本轮更新
- 首页缓存加载机制（HomeView）：
	- 新增前端缓存优先策略：页面挂载先读取本地缓存（`docscool.home.dashboard`）并立即渲染统计卡片与图表。
	- 缓存 TTL 设为 5 分钟，过期自动清理；缓存损坏场景自动移除并回退到后端请求。
	- 页面加载态调整为“整页级”：仅在“无本地缓存且后端数据仍在加载中”时显示 `正在加载中...`。
	- 后端返回后统一覆盖页面数据并回写缓存。
- 登录页视觉调整（LoginView）：
	- `login-panel` 样式调整为 `padding: 50px 30px`、`border-radius: 25px`。
	- 背景改为轻微半透明暗层 `rgba(0, 0, 0, 0.08)`，磨砂强度降为 `blur(1px)`（含 `-webkit-backdrop-filter`）。

### 2026-04-24 本轮更新
- 新增合同字段（全链路）：
	- 新增 `copy_count`（份数，纯数字整数，可为空）与 `save_place`（存档位置，文本，最大50字符，可为空）。
	- 后端已完成模型字段、启动期补列兼容、表重建路径同步与接口序列化返回。
	- 合同创建/更新与 Excel 导入均已接入字段校验：`copy_count` 仅允许整数；`save_place` 长度不超过 50。
	- 前端 `ContractItem`/`ContractView`/`FolderView` 已完成字段展示、编辑、保存、列表列与搜索联动。
	- Excel 导入模板已增加“份数”“存档位置”两列及填写说明。
	- AI 识别按需求未接入这两个字段（保持现状）。
- 合同字段与选项源治理：
	- 后端合同字段进一步收敛，持续移除历史遗留字段（如发票类型、税率、审批状态）的联动影响。
	- 合同类型、采购类型、计价方式、合同确定方式等下拉来源统一按 `CSV_OPTION_DEFAULTS` 静态返回（项目/部门继续走设置表）。
	- 合同金额 `contract_amount` 在前后端均改为非必填，空值可正常保存与更新。
- AI 识别金额规范化：
	- 完成 `backend/app/contracts.py` 中 `_find_amount` 金额解析增强：支持识别 `亿/万元/千元/元` 等单位并统一换算到“元”。
	- 结果统一量化到分（最多两位小数，四舍五入），并输出纯数字字符串。
	- 增加混合文本兜底清洗逻辑（如含货币符号、逗号、噪声字符）后再解析。

### 2026-04-22 本轮更新
- 文件/文件夹 API 拆分：
	- 将 `/api/folders/*` 相关接口从 `backend/app/contracts.py` 拆分到新文件 `backend/app/files.py`。
	- 在应用工厂 `backend/app/__init__.py` 注册新蓝图 `files_bp`。
	- 保持接口路径不变，前端调用无需改动。
- 后端结构修复：
	- 修复 `backend/app/contracts.py` 头部被破坏导致的语法错误（未闭合字典、误插入三引号注释等）。
	- 补回被截断的常量与辅助函数定义，恢复后端可编译状态。
- 运行验证：
	- 后端健康检查 `GET /api/health` 返回 `{"status":"ok"}`。
	- 前端 `http://127.0.0.1:5173/docs/` 可访问（200）。

### 2026-04-21 本轮更新
- PDF 识别链路增强（后端）：
	- 在 `backend/app/contracts.py` 完成 `_extract_ai_content_from_pdf(uploaded_file)`，实现 PDF 每页渲染 PNG 后调用讯飞通用文字识别（intsig）接口。
	- 按讯飞文档实现 HMAC-SHA256 鉴权参数生成（`host/date/authorization`），并处理识别返回体中的 `payload.recognizeDocumentRes.text`（base64）。
	- `whole_text` 优先，缺失时回退拼接 `lines[].text`。
	- 在 `_extract_pdf_text` 中接入“讯飞 OCR 优先回退链路”：直接提取失败时先尝试讯飞 OCR，失败再降级本地 RapidOCR。
- 讯飞配置接入（后端配置）：
	- 在 `backend/app/config.py` 新增 `XUNFEI_APP_ID`、`XUNFEI_API_KEY`、`XUNFEI_API_SECRET`、`XUNFEI_API_URL`。
	- 在 `backend/.env.example` 补充对应环境变量示例。
- 文件夹页拖放上传增强（前端）：
	- `frontend/src/views/FolderView.vue` 完成拖放上传行为扩展：
		- 拖放到左侧树节点：上传到该节点路径并高亮节点。
		- 拖放到左侧非节点区域：上传到当前目录。
		- 拖放到右侧任意区域：上传到当前目录。
	- 增加窗口级 `dragover/drop` 捕获兜底，防止浏览器默认打开 PDF。
- 运行验证：
	- 后端已重启并通过健康检查：`GET /api/health` 返回 `{"status":"ok"}`。

### 2026-04-20 本轮更新
- 首页图表后端接口补齐并联调：
	- 新增并修复 `GET /api/contracts/dashboard-charts`
	- 新增并修复 `GET /api/contracts/statistics`
	- 前端 `HomeView` 改为并行请求统计与图表数据，图表改为真实后端数据驱动
- 目录统计性能优化：
	- 新增 `GET /api/folders/file-count`，后端递归统计“当前目录+子目录”文件总数
	- `FolderView` 去除前端递归遍历目录的多次请求，改为单请求获取总数
	- 新增 `currentFileCount` 用于显示当前目录文件数量（不含子目录）
- 修复远程存储统计异常：
	- 修复 `folder_path=''` 时可能触发 Synology `错误码: 119` 的问题
	- 递归统计改为复用同一会话，并在 119 时自动重登后重试一次
- 运行侧问题处理：
	- 清理端口 `6000` 上历史旧进程后重启后端，修复“代码已改但接口仍404”的进程污染问题

### 2026-04-16 本轮补充更新
- 调整合同编辑/新建弹窗中的 `AI识别` 交互：
	- 点击按钮后会先弹出提示：`AI识别结果只会自动填写空白的字段`，约 5 秒自动消失
	- 若当前 `form.fullbody` 文本长度大于 20，则前端不再下载/解析 PDF，而是直接把 `fullbody` 提交给 `/contracts/ai-parse`
	- 仍然保持“只补空字段、不覆盖已填写字段”的表单合并策略
- 扩展后端 `POST /contracts/ai-parse`：
	- 新增 JSON `fullbody` 直解析模式，长度大于 20 时直接进入 AI 结构化流程
	- 未提供足够 `fullbody` 时，仍按原流程处理上传 PDF，并在必要时走 OCR
	- 当前 prompt 也要求 AI 返回整理后的 `fullbody`，用于纠正 OCR 文本中的顺序、换行和明显识别错误
- 验证结果：
	- 前端 `npm run build` 通过
	- 后端 `backend/.venv312/bin/python -m py_compile backend/app/contracts.py` 通过

### 2026-04-16 本轮更新
- 完成 `ContractView` 组件化重构落地：
	- 新增 `frontend/src/components/ContractItem.vue`，承接合同新建/编辑/预览、文本弹窗、链接文件与 AI识别等能力
	- 新增 `frontend/src/components/AiMatchDialog.vue`，承接 AI 识别候选确认与预览
	- `frontend/src/views/ContractView.vue` 改为组合接线，减少大页内联逻辑
- 完成 `FolderView` 工作流增强：
	- 文件列表“合同名称”列改为真实匹配合同可点击打开编辑
	- `<无匹配>` 行新增“新建/AI”入口，可直接基于当前文件路径发起流程
	- 新增目录级“上传文件”能力，支持多文件上传到当前目录
	- 新增左右面板可拖拽分隔条（桌面端）
	- 接入 `ContractItem` 时隐藏“上传文件/链接文件”，并提供“解绑合同”动作
	- 新建并带文件路径时，进入弹窗即尝试加载预览
- 完成后端目录接口扩展：
	- 新增 `POST /folders/upload` 用于目录多文件上传
	- 新增 `POST /folders/batch-match` 用于目录批量匹配
- 完成批量匹配规则强化（最新约束）：
	- 仅处理“没有关联合同”的文件
	- 对已有关联合同的文件返回 `skipped` 状态并记录已关联的合同信息
- 运行验证：
	- 前端 `npm run build` 通过（仅存在 chunk 体积告警）
	- 后端语法编译通过
	- 后端服务可用 `backend/.venv312/bin/python backend/run.py` 正常启动

### 2026-04-15 本轮更新
- 在合同编辑/新建弹窗左侧“文件预览”区域上方新增“AI识别”按钮：
	- 当存在当前预览文件（包括：已上传合同 PDF、通过“链接文件”选择的 NAS PDF、或本次新建时尚未保存但已选择的本地 PDF）时可点击
	- 内部复用后端 `POST /contracts/ai-parse` 接口，将当前文件提交 AI 解析
	- 解析结果通过 `applyAiSupplementalFields()` 仅补全表单中原本为空的字段，不覆盖用户已手工填写的内容
	- 若解析结果包含 `fullbody`，也会写入 `form.fullbody`，与“AI上传”路径保持一致
- 链接文件弹窗 (`linkFileDialogVisible`) 的 PDF 预览与主编辑预览已打通：
	- 通过“链接文件”选择 NAS 目录下的 PDF 后，确认会同步更新主弹窗的 `form.file_path` 与左侧预览
	- 若链接的并非 PDF 文件，则在预览区域给出“该文件不是PDF，无法预览”的提示，仍可通过“下载原文件”按钮获取原始文件
	- 全屏预览入口同时支持“AI上传”预览和“链接文件”预览

### 2026-04-14 本轮更新
- 完成后端默认部门保底逻辑：
	- 应用启动时会自动补齐 `财务部`
	- 部门设置接口禁止删除默认部门 `财务部`
- 确认本地后端兼容启动方式：
	- 由于当前 `.venv` 为 Python 3.14，`rapidocr-onnxruntime` 不兼容
	- 已改用 `backend/.venv312` 启动后端并验证 `GET /api/health` 正常
- 更新合同列表/导入区前端交互：
	- 合同编号列改为单行省略显示
	- 顶部“导入Excel”按钮改为 Excel 文件图标
	- 导入弹窗中“下载模板”改为 link 样式
	- 导入弹窗中“选择文件”按钮图标改为通用文件图标
- 当前前端仍存在一个已有模板语法问题：
	- `frontend/src/views/ContractView.vue` 中 `@click.stop="javascript:void(0);"` 会触发模板编译报错

### 2026-04-03 当前阶段
- 启动并验证本地开发环境：
	- 后端开发服务运行在 `http://127.0.0.1:6000`
	- 前端开发服务运行在 `http://127.0.0.1:5173/docs/`
- 完成合同金额精度升级：
	- 后端 `Contract.amount` 从 `NUMERIC(12, 2)` 升级为 `NUMERIC(20, 8)`
	- 新增 SQLite 迁移脚本 `backend/scripts/migrate_contracts_amount_precision.py`
	- 前端金额输入与首页汇总改为保留高精度字符串处理，避免 JS 浮点误差
- 完成 EXCEL 导入链路：
	- 后端支持 `xls` / `xlsx` 导入
	- 支持导入模板下载
	- 支持失败明细导出
	- 已适配真实 `xls` 文件读取
- 完成 AI 上传识别结果确认流程：
	- AI 上传后不再直接打开新建窗口
	- 先弹出“识别结果确认”窗口
	- 展示候选合同列表，并区分“已有合同” / “这是新合同”
	- 候选列表新增“匹配依据”列
	- 候选窗口左侧增加上传文件 PDF 预览，并支持全屏查看
- 完成 AI 候选匹配策略升级：
	- 先按金额相同优先
	- 再按标题相似度降序补足最多前 5 个候选
	- 已做去重处理
- 完成合同全文 `fullbody` 能力：
	- 后端合同模型新增 `fullbody` 长文本字段
	- SQLite 启动时自动补列 `fullbody TEXT`
	- `POST /api/contracts/ai-parse` 返回顶层 `fullbody`
	- 新增 `GET /api/contracts/<id>` 详情接口，专门返回含 `fullbody` 的详情
	- 创建合同、更新合同都已支持保存 `fullbody`
	- 列表搜索已支持命中 `fullbody`
- 完成前端 `fullbody` 展示与保存：
	- 新建/编辑弹窗预览区增加“文本”按钮
	- “文本”按钮打开纯文本弹窗，绑定 `form.fullbody`
	- 新建保存、编辑保存都会提交 `fullbody`
	- 编辑已有合同会先请求详情接口，确保读取到 `fullbody`
- 修复前端 `fullbody` 丢失问题：
	- 问题现象：`ai-parse` 能返回 `fullbody`，但进入编辑框后点击“文本”看不到内容
	- 根因：前端只把 `fullbody` 放进 `aiParsedFullbody`，而进入匹配编辑链路时实际传递的是 `aiParsedFields`，对象内原本没有 `fullbody`
	- 修复方式：将 `data.fullbody` 合并进 `parsedFields`，并在 `applyParsedFields()` 中统一写入 `form.fullbody`
	- 修复后前端构建已通过

## 当前已确认的实现约定
- 合同列表接口默认不返回 `fullbody`，避免长文本拖慢列表加载。
- 编辑合同时，如果需要正文内容，前端必须调用详情接口 `/api/contracts/<id>`。
- 前端开发代理已改为指向 `http://127.0.0.1:6000`。
- 新建合同时如果先选择文件但合同尚未保存，文件会暂存为待上传状态，保存合同后再自动上传。

## 当前待继续关注项
- EXCEL 导入仍建议补“预检不落库”模式。
- 导入失败明细目前使用进程内存暂存，后续可改为带过期策略的临时文件。
- `fullbody` 已可保存和显示，后续仍建议做一轮真实 PDF 联调回归。
