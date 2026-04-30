# 待完善任务清单

更新时间：2026-04-29

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
