# 0902精简快照接入与数据库迁移记录

日期：2026-11-10。范围依据：用户授权将run_id改为task_id，保留input_revision和snapshot_schema_version，调整现有快照表并与sc_file_item同事务保存，暂不做0903。业务权威仍为[实施方案](../rule-normalization-plan-20261105/实施方案.md)及[接入细则§4.3](../rule-normalization-plan-20261105/项目接入实施细则.md)，本报告只记录实现与验证，不另立业务方案。

## 已完成

- 已在当前测试库`10.1.40.154:5432 / cq_smart_cost / public`应用增量迁移002，并通过新连接核验。快照表仍为10列，task_id替代run_id；输入版本、结果版本、格式版本与唯一约束保留。
- 新增`sc_file.input_revision`及表头/原始行触发器，作为快照输入修订号的真实来源；现存169个文件从迁移基线1开始，不编造此前的修改历史。普通行级增删改参与同一数据库事务，同值UPDATE不增号。版本不是用户操作次数；管理性TRUNCATE、禁用触发器或手工重置版本不属于受支持的输入写入路径。
- 0902 Runner先读取一致输入，沿用原模型、结构、计量、分类和CBS流程；同一次构建返回工程量及合并完成后的全行映射，再构建和校验快照。
- 保存事务依次复核任务/请求、文件归属、输入修订与指纹，分配文件结果版本，清理原有成果及受影响下游，写入17列工程量，按数据库实际值固定快照，追加快照，更新2102。任一步失败整体回滚；不同文件仍逐个提交。
- 快照包含原始业务输入、完整结构与证据、pending及未知字段、原行顺序、保留/合并映射、工程标题来源、计量基数与倍率、计算原值及数据库实物量。Decimal按精确字符串存JSON。持久化不新增模型调用，不把存储版本字段加入Prompt。
- 旧版本快照保留；重做追加result_revision，失败续跑不覆盖已完成文件。request_id在正文中保存并继续参与原有请求校验；task_id仅追溯既有任务，不代替完整逻辑run。

主要文件：

| 文件 | 变更 |
|---|---|
| `smart-cost-ai/ai_service.py` | 新增FileBuildResult/build_file_result，保留原列表接口；同步返回最终来源映射，不重建第二套item ID |
| `smart-cost-ai/analysis_snapshot.py` | 构建、格式/来源/覆盖校验、输入与结果指纹、持久化精度固定 |
| `smart-cost-ai/schemas/file-analysis-snapshot.schema.json` | 正文格式1.0合同，随Runner一并部署 |
| `smart-cost-ai/repository.py` | 短事务读取、锁内输入复核、结果版本分配与原子保存 |
| `smart-cost-ai/runner.py` | 接入同一次构建的快照保存 |
| `smart-cost-server/src/main/resources/db/migrations/20261110_002__enable_0902_snapshot.sql` | 改名、真实输入修订字段及触发器 |
| `smart-cost-ai/tests/test_analysis_snapshot.py`、`test_repository_pg.py`、`test_config_runner.py` | 新增快照行为与故障测试，调整现有Runner/保存夹具 |

现有quantity、classification、chunking、cbs_matching及Prompt算法本轮未改；未新增Java实体、前端功能或0903处理器。

## 验证结果

| 检查 | 结果与边界 |
|---|---|
| Python默认全套回归 | 共发现277项：244项通过，33项PG用例因默认开关跳过；12.141秒 |
| PostgreSQL专门运行 | 上述33项全部通过；2.307秒。只使用会话临时表及临时函数/触发器，不写共享业务成果 |
| 正常Runner回放 | 通过真实Repository及PostgreSQL临时表，保存完整快照、工程量及2102；既有3次模型请求以固定响应回放，无额外请求 |
| 源码与配置 | 生产模块语法检查通过；`runner.py --check-config`通过，该命令不连库、不调用模型 |
| 实际库迁移 | 已提交并由新连接核验：task_id存在、run_id消失、输入计数列存在且为正、两个触发器启用、约束保留 |
| 实际料表/模型/UI | 未执行；未自动重算、回填历史文件，未启动或重启常驻Runner |

两轮测试合计覆盖277个不同用例，不把PG重跑重复计数，不据此宣称业务金标准确率或提速比例。

关键断言包括：

1. summary、note、project、pending等非出表结构及证据仍完整保留；空实物成果也可保存上下文。
2. 绝缘子串合并后子件不再独立出表，merged_into指向真实母项；倍率只计算一次，实物量与numeric(18,6)落库值一致。
3. 同名不同project源行保持不同实例锚点；没有工程或逻辑表依据时保留UNKNOWN，不从CBS猜测。
4. 快照INSERT故障恢复旧工程量、下游关联及状态；原有实物INSERT和状态UPDATE故障回滚用例继续通过。
5. 模型运行期间输入变化拒绝保存；即使错误重置版本号，内容指纹仍能拒绝变化的原文；请求被替换也拒绝旧请求提交。
6. 表头/原始行触发器随事务回滚；同值UPDATE不增号；输入短事务结束后连接空闲。
7. 重做追加版本并保留旧原文与旧结果；第6份失败后只续跑剩余5份，前5份和其快照保持不变。

命令从`E:/smartCost/smart-cost-ai`执行：

```powershell
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s tests -v
$env:SMART_COST_AI_PG_TEST = '1'
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s tests -p test_repository_pg.py -v
.venv/Scripts/python.exe -B -X utf8 runner.py --check-config
```

测试输出：[离线日志](offline-tests.log)、[PostgreSQL日志](postgres-tests.log)。迁移记录：[migration-result.json](migration-result.json)。迁移002的SHA-256为`d8e7c473cc5766bd69b87826547c91399f536060d9ed42a912969be6b4d3ec64`；001及其原始执行证据未改写。检查时实际快照表记录数为0，后续正常0902才生成业务快照。

## 部署、回退及保留边界

其他环境先核对现库，再依次应用尚未执行的001/002，随后部署Python和Schema、检查配置、启动Runner。002要求快照表为空，非空时停止，不能把旧run_id直接解释成task_id。当前库已经应用，不应重复执行；正常启动入口仍为`smart-cost-ai/runner.py`。

写入器不提供“快照失败但工程量成功”的降级分支。若新增保存异常或来源映射不一致，停止受影响文件并保留旧成果；修复后按ADR-0006选择失败续跑或明确重做。回退保留DDL、版本计数和历史快照；不得静默恢复旧版只写工程量的写入器。整体撤回功能时先停用任务处理，再明确恢复范围。

本轮完整保存当前0902已经能够证明的结构；逻辑表边界缺失仍为UNKNOWN。显式project锚点不等于已确认的完整A06分组，没有提前选择A06末行。供货范围未判定时也为UNKNOWN，不能因为已合并就推定业务包含关系。

人工修改工程量不会生成新快照，旧快照仅对应原提交成果；完整run/STALE、当前有效版本选择、人工编辑失效和清理保留策略仍待后续实现。0903消费前必须复核版本、当前实物指纹、完整分组及必要参数；不能默认最大result_revision就是有效上下文。历史文件不因升级自动改动。本次程序测试不能替代规则验收登记按2026-11-10新业务口径重编，也不能代表§18全部完成。

修改前文件副本与指纹在`baseline/`及[baseline-fingerprints.json](baseline-fingerprints.json)；最终变更清单见[implementation-manifest.json](implementation-manifest.json)，相对本轮基线的文本差异见[changes.diff](changes.diff)。
