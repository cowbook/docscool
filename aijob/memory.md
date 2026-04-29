# AI 工作记忆

更新时间：2026-04-29

## 使用约定
- 本文件用于记录 AI 已完成、已确认、待回归的重要工作，按时间顺序持续追加。
- 后续 AI 在继续开发前，优先阅读本文件，避免重复判断、重复改动和遗漏既有约定。
- 记录应以“已验证事实”为主，尽量避免写未经确认的猜测。

## 时间线

### 2026-04-29 本轮更新
- HomeView 首页响应式与右侧“最新上传”区域优化：
	- `latest-grid` 已从固定列 Grid 改为可换行 Flex，自适应一行展示数量。
	- 缩略图尺寸上限调整为 `168x232`（原 `210x290` 的 80%），避免窄屏挤压。
	- 缩略图增加悬停放大效果（hover/focus），并增加边框高亮与阴影反馈。
	- 断点按常用宽度微调（1366/1024/768/390），中屏保持左窄右宽布局，避免左侧主区占满。
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
