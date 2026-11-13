# 项目级费用功能撤除记录

2026-11-13，按[用户确认](用户确认.md)移除 `sc_project_cost_object` 对应的自动项目级费用功能。当前权威入口更新为主方案v1.20、细则及验收v1.15；旧版本登记仍作为历史资料，不再作为当前开发要求。

## 变更

- 0903拟新增表从三张减为两张：`sc_file_quota_snapshot`、`sc_match_revision`。删除项目费用表的字段、唯一键及专用代次设计，D4拟迁移改为`008__0903_quota_snapshot.sql`。
- 删除费用生成器、Java费用模型/DAO/DTO、费用查询API、前端费用结果调用及相关测试文件的开发要求。在线基线模块由15个减为14个，拟新增Java文件由13个减为10个。
- A06-R084/R085/R086即使命中且费用参数齐全也跳过；不执行对应金额公式、不生成费用记录或NEEDS_INPUT待补，不追加外部调用或专用补参入口。该范围决定不允许通过恢复任务重新启用。
- 保留正常A09项目路线、文件内A06关联与任务恢复。原项目费用提交步骤改为只核固定工作集及全批当前依赖的任务完成证明，避免删费用功能时一并删掉完成/恢复保障。
- 同步更新完整0903实施提示词。验收保留302个ID（298当前适用、4历史），修订T36/T53/T54/Q27/Q28/Q37/Q41/Q62/Q80九项定义，按最终两份Markdown重新绑定来源行、预期与SHA-256。

## 实际实现状态与验证边界

在Python业务源码、Java/Vue代码和实际SQL中未发现该表的建表或业务读写实现；`project_fees.py`及ProjectCostObject系列文件仍是此前方案中的拟开发文件。因此本次实际变更是实施基线、开发清单、派生验收和提示词，没有声称删除不存在的运行代码。

离线v5仍保留251条原规则，包含三项费用的历史表达；它们不再授权当前0903执行对应动作。v5及离线编译工具未改，不在已有发行目录中改写内容或重发同名版本。加载器仍校验原规则包的完整性，执行能力校验按当前范围处理。

静态检查入口为`verify_documents.py`，结果见[checks.json](checks.json)：核对302条登记、9项预期变更、门槛登记来源、移除引用、表/模块/Java文件数量、业务源码及发行字节保护、v5声明文件哈希。全部业务用例保留NOT_RUN，不把文档检查计为0903验收。

未连接数据库核查物理现状，未执行DROP TABLE、Dify、模型、业务测试或服务重启，未提交SVN。

## 文件与后续使用

- 当前主方案：`E:/smartCost/verification-evidence/rule-normalization-plan-20261105/实施方案.md`
- 当前细则：`E:/smartCost/verification-evidence/rule-normalization-plan-20261105/项目接入实施细则.md`
- 当前验收：`E:/smartCost/verification-evidence/rule-normalization-plan-20261105/acceptance-cases.v1.15.json`
- 当前检查：`E:/smartCost/verification-evidence/rule-normalization-plan-20261105/baseline-integration-checks-v1.15-20261113.json`
- 实施提示词：`E:/smartCost/verification-evidence/20261112-0903-second-review-integration/Codex-0903完整实施提示词.md`

变更前的三份文档原始字节保存在本目录`before/`。恢复这些历史文件会同时恢复旧费用开发要求，因此只有用户重新明确授权该功能时才可调整当前执行范围；不能由程序错误回退或旧提示词自动恢复。
