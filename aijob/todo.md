# 待完善任务清单

更新时间：2026-05-12

## 0.7 本轮新增回归项（附件筛选与部门候选）
- 合同列表筛选回归：
	- 回归三态附件筛选 `全部 / 无附件 / 有附件`。
	- 回归 `GET /api/contracts` 对 `has_file=false` 的真实筛选结果。
- 承办部门下拉回归：
	- 回归列表页部门下拉对“数据行里存在但部门表中不存在”的值补齐展示。
	- 回归编辑/新建弹窗中的部门下拉仍仅使用配置表，不受列表页补齐逻辑影响。
- 导航菜单回归：
	- 回归主导航“系统设置”不再显示“密码修改”和“退出”。
	- 回归右上角用户菜单是否仍保留上述两个入口，按当前约定保持不变。

## 0.8 本轮新增回归项（2026-05-11 深拆后保存链路）
- 合同保存回归：
	- 回归 `POST /api/contracts` 在常见合同类型输入下不再触发运行时错误。
	- 回归 `contract_type` 相关字段保存与 `stamp_tax_rate` 联动逻辑。
- 合同更新回归：
	- 回归 `PUT /api/contracts/<id>` 修改 `handling_department` 时不再触发 `_department_dir` 未定义错误。
	- 回归“部门不在配置表中”场景应返回 400 业务错误而非 500。
- 重构稳定性回归：
	- 回归 `contracts_routes_contracts_helpers.py` 与 `files_core_helpers.py` 拆分后导入关系完整。
	- 回归 `create_app` 启动、`py_compile`、核心路由注册均正常。

## 0.9 本轮新增回归项（2026-05-12 快速匹配与凭据过期）
- 快速匹配接口回归：
	- 回归 `POST /api/contracts/quick-match-files` 在凭据过期场景返回 401，不再返回 500。
	- 回归 `_select_best_pdf_match` 精确命中路径下返回结构稳定，`similarity` 字段可用。
	- 回归部门路径优先筛选分支不再出现 `handing_department` 属性错误。
- 前端自动退出回归：
	- 回归合同列表页“快速批配 -> 开始”遇到 401/凭据过期消息后自动清 token 并跳转登录。
- AI 解析回归：
	- 回归 `POST /api/contracts/ai-parse` 不再出现 `EXTERNAL_API_TIMEOUT_SECONDS` 未定义错误。
- 导入弹窗交互回归：
	- 回归“选择文件”后按钮立即变为“导入中...”，且在导入完成前不可点击。

## 0.4 本轮新增回归项（OCR模块化与导入模板下载）
- OCR 模块化回归：
	- 回归 `contracts.py` 调用 `ocr_utils.py` 后，`/api/contracts/ai-parse` 在文件上传与 fullbody 直解析两条路径行为一致。
	- 回归 RapidOCR、讯飞 OCR、MinerU OCR 的失败回退链路与错误提示文案。
	- 回归 `MINERU_API_KEY` 缺失场景的报错可读性。
- 导入模板下载回归：
	- 回归 `GET /api/contracts/import-template` 在后端 200 时前端可正常触发浏览器下载。
	- 回归 `content-disposition` 含 `filename*`（UTF-8）与 `filename=` 两种格式的文件名解析。
- 首页角标样式回归：
	- 回归 `HomeView` 右上角角标为直角三角形切角，不影响点击打开绑定合同。
	- 回归角标半透明底色在浅色/深色缩略图上的可见性。

## 0.5 本轮新增回归项（加载态与样式作用域）
- 合同编辑加载态回归：
	- 点击合同名称后应立即弹出编辑框并显示“加载中...”，不得出现空白等待。
	- 详情加载完成后再展示完整表单；失败时关闭弹窗并提示错误。
	- 加载期间“保存/解绑”按钮应禁用。
- AI 候选弹窗加载态回归：
	- AI 上传后应立即打开候选弹窗并显示“加载中...”，候选列表在数据返回后渲染。
	- 加载期间“下一步”按钮应禁用，避免误提交。
- 全屏预览状态文案回归：
	- 文档准备中显示“预览加载中...”。
	- 仅在无可预览文件时显示“暂无可预览内容”。
- 样式作用域回归：
	- 验证 `.el-scrollbar` 的补丁样式仅在合同页生效，不得影响用户菜单和各类 `el-select` 下拉高度。
- 按钮组视觉回归：
	- 顶部操作按钮组需保持阴影、首尾圆角、按钮分隔线与 hover/active 反馈一致性。

## 0.3 本轮新增回归项（最新上传修改人与首页缩略图布局）
- 最新上传接口回归：
	- 回归 `GET /api/folders/latest-uploads` 的 `modified_by` 必须来自文件系统元数据，不再受合同 `handler/created_by` 影响。
	- 本地模式下验证返回值稳定（无 owner 信息时兜底 `-`）。
	- 远程 Synology 模式下验证 owner 字段解析稳定（用户名/组名/uid 兜底顺序）。
- 首页最新上传布局回归：
	- 回归 `HomeView` 的 `.latest-grid` 为 Flex 自适应换行，不再固定列数。
	- 回归缩略图上限为 `168x232`，并验证 hover 放大不溢出容器。
	- 回归缩略图 hover/focus 时图框上浮（`translateY(-6px)`）与阴影过渡效果。
	- 回归 1366/1024/768/390 四档宽度下卡片排布与可读性。
	- 回归金额卡片“总金额/归档金额”单位样式：单位需为浅色 `14px`，数字与单位分段渲染。

## 0.2 本轮新增回归项（files.py 拆分）
- 路由回归：
	- 回归 `/api/folders/*` 全量接口（tree/children/files/file-count/upload/batch-match/rename/delete/download/preview）在拆分后行为一致。
	- 验证鉴权失败、路径非法、文件不存在等错误码与文案保持一致。
- 运行回归：
	- 回归 `files_bp` 注册后与 `contracts_bp` 无路由冲突。
	- 回归前端 FolderView 全链路（上传、批量匹配、重命名、删除、预览、下载）。
- 代码整理：
	- 后续可继续下沉 `contracts.py` 内被 `files.py` 复用的辅助函数，减少跨模块私有函数依赖。

## 0. 本轮新增回归项（目录统计与首页图表）
- 首页回归：
	- 回归 `GET /api/contracts/statistics` 与 `GET /api/contracts/dashboard-charts` 的鉴权、空数据、异常数据场景
	- 回归 `HomeView` 在后端不可用时的错误提示与降级展示
- 目录统计回归：
	- 回归 `GET /api/folders/file-count` 在空目录、深层目录、无权限目录下的返回
	- 远程模式下验证 Synology 会话失效自动重登逻辑（错误码 119）
	- 评估超大目录统计耗时，必要时增加缓存或异步统计

## 0.1 本轮新增回归项（讯飞 OCR 与拖放上传）
- 讯飞 OCR 回归：
	- 验证 `_extract_ai_content_from_pdf` 在多页 PDF 下的逐页识别结果拼接是否稳定。
	- 验证 `XUNFEI_*` 缺失时错误提示是否可读且不影响 RapidOCR 回退。
	- 验证讯飞鉴权失败（401/403）时日志定位信息是否充分。
	- 验证 `payload.recognizeDocumentRes.text` 解码后 `whole_text` 缺失场景的 `lines` 回退逻辑。
- 文件夹拖放上传回归：
	- 左侧树节点、左侧非节点、右侧任意区域三类拖放目标均应按预期目录上传。
	- 验证拖放 PDF 时浏览器不再触发默认打开文件行为。
	- 验证拖放并发与上传中重复拖放时的状态（loading/提示）是否正常。

## 1. 合同编辑弹窗 AI 识别回归
- 当前位置：`frontend/src/views/ContractView.vue`
- 新增按钮：编辑/新建弹窗左侧“文件预览”上方 `AI识别`
- 行为：点击后先提示“AI识别结果只会自动填写空白的字段”；在存在预览 PDF 时调用 `/contracts/ai-parse`，只补空字段，不覆盖已有值；若 `fullbody` 已超过 20 字符则直接提交文本跳过 OCR
- 后续回归项：
	- 使用真实 PDF 验证“AI上传”与“AI识别”两条链路兼容且字段一致
	- 验证已有 `fullbody` 的合同会直接走文本解析分支，并且不会再触发 OCR 下载链路
	- 验证链接 NAS 文件、直接上传本地文件两种场景，都能正确触发预览和识别

## 2. 统一本地后端启动入口
- 当前稳定方式是使用 `backend/.venv312/bin/python run.py`
- 后续可补：统一启动脚本、VS Code task、README 本地启动说明

## 3. 批量匹配能力继续增强
- 增加“匹配预演（不写库）”模式，先展示将要绑定的合同清单
- 增加可选策略：只允许 `exact` 或允许 `contains-*`
- 增加结果导出（CSV）便于审计

## 4. EXCEL 导入继续回归
- 验证导入规则提示是否与当前后端实际校验一致
- 用真实 MIS 导出文件再做一轮导入与失败明细验证

## 5. 新字段回归（copy_count / save_place）
- 后端回归：
	- 回归 `POST /api/contracts` 与 `PUT /api/contracts/<id>`：`copy_count` 允许空、非空时仅允许整数；`save_place` 允许空、长度超过 50 时应报错。
	- 回归 `GET /api/contracts`、`GET /api/folders/files` 返回新增字段且兼容历史数据空值。
- 导入模板与导入回归：
	- 回归导入模板包含“份数”“存档位置”列与填写说明。
	- 回归 Excel 导入在两字段为空、合法、非法（非整数/超长）场景下的行为与报错文案。
- 前端回归：
	- 回归 `ContractItem` 新建/编辑保存时字段提交正确。
	- 回归 `ContractView` 与 `FolderView` 新增列表列展示与搜索命中。

## 6. 首页缓存加载机制回归（HomeView）
- 首屏行为：
	- 本地存在未过期缓存时，页面应直接渲染缓存数据，并后台刷新。
	- 本地无缓存时，后端请求未完成前应显示整页 `正在加载中...`。
- 缓存时效：
	- 缓存超过 5 分钟应判定过期并移除。
	- 缓存 JSON 损坏时应自动清理，不得阻塞页面渲染。
- 接口异常：
	- 后端请求失败时应提示“统计数据加载失败”，并保持已有缓存数据可见（若存在）。

## 7. 登录页样式回归（LoginView）
- 回归 `.login-panel` 关键样式：
	- `padding: 50px 30px`
	- `border-radius: 25px`
	- `background: rgba(0, 0, 0, 0.08)`
	- `backdrop-filter: blur(1px)`（含 webkit 前缀）
