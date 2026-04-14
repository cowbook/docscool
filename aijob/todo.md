# 待完善任务清单

更新时间：2026-04-14

## 1. 修复 ContractView 模板语法错误
- 当前位置：`frontend/src/views/ContractView.vue`
- 问题代码：`@click.stop="javascript:void(0);"`
- 现象：前端检查会报 `';' expected.`

## 2. 统一本地后端启动入口
- 当前稳定方式是使用 `backend/.venv312/bin/python run.py`
- 后续可补：统一启动脚本、VS Code task、README 本地启动说明

## 3. EXCEL 导入继续回归
- 验证导入规则提示是否与当前后端实际校验一致
- 用真实 MIS 导出文件再做一轮导入与失败明细验证
