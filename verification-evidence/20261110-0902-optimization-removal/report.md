# 0902未达门槛优化代码撤除与验证

2026-11-10。根据用户“如果优化没用，就把对应优化代码去掉，并将方案更新”的指令，已从正常运行目录撤除OPT01、OPT02、OPT04、OPT05及OPT09中的CBS并发实现。正常Runner已切换为完整对象输出、逐请求独立HTTPS、结构chunk/CBS范围/文件串行。本轮不部署隔离数值修复，不实施0903/0904，不调整OPT03窗口，不自动重试旧任务。

这是既有方案的实际变更记录，不另立实施方案。没有证据证明这些实现当前有可启用的质量/性能收益；这不代表这些技术在所有场景中都不可能有效。

## 1. 撤除依据与性能边界

历史42份真实单因素试点包括模型与PG临时表提交，冷/热各3次，固定8行输入。相对同代码全关control，各因素的观测p95均没有改善：

| 因素 | cold p95秒 | warm p95秒 | 当前处理 |
|---|---:|---:|---|
| 全关control | 11.278 | 11.569 | 作为原处理路径对照 |
| 模板/Schema预加载 | 11.340 | 12.096 | 撤除 |
| 原文解析/结构索引 | 11.446 | 19.303 | 撤除 |
| 请求JSON压缩 | 16.185 | 16.754 | 撤除 |
| 15字段紧凑编码 | 13.578 | 13.321 | 撤除 |
| HTTPS连接池 | 12.086 | 18.224 | 撤除 |
| CBS范围并发大于1 | 未跑 | 未跑 | 依赖未满足，未有真实收益证据，撤除调度器 |

原始分母、主断言质量结果和Token见[历史性能表](../20261110-0902-optimization/performance-table.md)及[原报告](../20261110-0902-optimization/report.md)。每格n=3且质量门槛未通过，不能把这些数当成稳定的生产差异。真实费用仍UNKNOWN，没有可核验账单，不能用Token代替费用声称降本。

原全关20份任务全部执行完成，既有日志领取到任务结束617.946秒；优化试用首文件失败，20份未得到同条件完整耗时，不能给出这20份的有效提速比例。后续紧凑纠正候选的南湾村6份真实试验：主断言1通过、3质量失败、2执行失败，独立完整语义确认0/6；候选未部署，见[原复验](../20261110-0902-codec-repair/report.md)。本轮新增真实模型调用0次、费用0笔新增请求；未做新性能/TTFT/UI首次可见时间测量，不以本轮离线耗时宣称提速。

## 2. 源码与具体改动

SVN工作副本未提交新版本，保留所有既有修改，以内容指纹交接。撤除前26个运行源码/模板文件、全部测试、25个旧preview文件及权威文档分别保存在`before/`。本地正常秘密配置仅记录哈希，没有改动或输出密钥。

当前21个运行文件集合指纹：`86d9b5aabcc246be7ebd2f83a47643677680adb87594463349b274284ca189d2`。算法是对按相对路径排序的SHA-256映射使用`analysis_snapshot.fingerprint`，逐文件明细见[cutover.json](cutover.json)、[installed-verification.json](installed-verification.json)。

| 条款 | 实际变更 |
|---|---|
| §20.2 / OPT01 | 删除`preparation.py`和ai_service/quantity/CBS的准备缓存装饰器、绑定及结构索引读取；恢复原解析/祖先遍历。 |
| §20.2 / OPT02 | 删除压缩分支和静态内容省略；使用原JSON格式，完整保留输入和输出约束。 |
| §20.3 / OPT04 | 删除`compact_codec.py`及编码、解码、纠正分支；只有原完整对象Schema，15字段及分类证据不变。 |
| §20.5 / OPT05 | 删除`http_transport.py`连接池；每请求新建/关闭HTTPS，保留鉴权目标、参数、超时、拒答、截断、request_id、usage、脱敏和不隐式重试。 |
| §20.4 / OPT09部分 | 删除`scope_scheduler.py`；CBS范围按原顺序串行，范围内叶子→父工程→必要复核依赖不变。 |
| §22 / 最小配套 | 删除`optimization.py`、Config运行开关对象与实验准入分支；旧false/整数1仅兼容解析，true或非法值调用前拒绝。保留execution_profile的源码/模型/规则/CBS冻结和提交保护。 |

运行目录改动8文件：`ai_service.py`、`cbs_matching.py`、`quantity.py`、`config.py`、`config.example.json`、`execution_profile.py`、`repository.py`、`runner.py`。删除上述5个优化模块。新设/适配5个测试模块，8个仅服务已撤除实现的测试模块归档后移出当前测试集合；其中仍适用的传输、业务、串行范围和事务断言迁入现有/新回归。

完整修改/删除及逐文件SHA-256见[delivery-files.json](delivery-files.json)，运行代码逐行差异见[runtime-removal.diff](runtime-removal.diff)。

`classification.py`、分类规则、`chunking.py`、`analysis_snapshot.py`、全部prompts/业务Schema共11文件指纹未变。保留summary、pending、assembly/component、原数量枚举与绝缘子合并、分类理由/来源、SUMMARY_ROLE_CONFLICT、CBS全候选/同名展开/父ID去重/完整路径/possible竞争。结构和文件失败不提交半份数据。

旧`smart-cost-ai-preview/`可执行副本已归档移除，仅留退役说明；旧`preview_service.py`启动即以非零状态拒绝，见[退役入口检查](preview-retired-check.log)。旧本地实验配置移出正常目录，STOP保留，状态登记RETIRED。历史验证目录中的候选和日志作为审计证据保留，不是当前运行入口。

## 3. 实际测试

在`E:/smartCost/smart-cost-ai`执行：

```powershell
$env:SMART_COST_AI_PG_TEST='1'
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s tests -v
```

| 验证层 | 通过 / 失败 / 跳过 | 实际证据 |
|---|---:|---|
| 撤除候选完整程序回归 | 300 / 0 / 0 | [tests-pg-final.log](tests-pg-final.log)，15.703秒 |
| 实际运行目录完整复验 | 300 / 0 / 0 | [installed-tests.log](installed-tests.log)，14.745秒；含44项真实PG临时表测试 |
| 原20份真实响应离线差分 | 20 / 0 / 0文件 | [replay-summary.json](replay-summary.json)，101响应、449原行、306条各17列工程量 |
| 新真实模型/真实任务流程 | 未跑，不计通过 | 本轮只撤除代码，没有申请或使用新的外发额度 |

两次300是同一用例集合的候选及安装后复验，不能加总成600个不同用例。首次未开PG的预检为256通过/33跳过，后续开启全部PG；中间300项有1个旧夹具遗漏freeze步骤而失败，已显式补齐后保留原拒绝断言。中间日志保留，没有擦掉失败或把SKIPPED当通过。

临时表测试覆盖工程量/快照/文件同事务、快照故障回滚、请求/输入/CBS变化拒绝、已完成5文件及人工结果保护、同版本续跑、旧优化/旧指纹/旧无冻结任务拒绝、新普通任务不受已退役优化禁用开关影响。模型超时、断连、429、拒答、截断和并发日志是确定性故障注入，不冒称供应商真实故障演练。

离线差分复现命令（工作区根目录）：

```powershell
smart-cost-ai/.venv/Scripts/python.exe -B -X utf8 verification-evidence/20261110-0902-optimization-removal/replay_successful_files.py before
smart-cost-ai/.venv/Scripts/python.exe -B -X utf8 verification-evidence/20261110-0902-optimization-removal/replay_successful_files.py candidate
```

重放保留真实`call_model`的HTTP请求构造，替代HTTPS连接并禁止socket联网。逐次核对原记录完整请求及Schema；响应只替换随机packet/context标识，结果随机ID使用确定性序列，审计字段使用两版一致的测试值。两份结果文件逐字节一致：`20dab8cc0e69b798ed117c6c385cb244f673a7829350834e5ad61d51a0ddc33c`。这是程序等价证据，不证明旧模型全部语义正确，也不是新真实质量测试。

## 4. 运行状态与数据保护

2026-11-10 20:49（Asia/Shanghai）最终启动正常Runner，启动器19052、worker48500；启动记录见[runner-final.stderr.log](runner-final.stderr.log)。启动命令为：

```powershell
cd E:/smartCost/smart-cost-ai
.venv/Scripts/python.exe -B -X utf8 runner.py --config config.application.local.json --check-config
.venv/Scripts/python.exe -B -X utf8 runner.py --config config.application.local.json
```

当前进程已运行，不要重复启动第二个Runner。下一次操作仍先核对进程及活动任务。本轮没有改Java8080、前端5173或Dify；没有触发0903。

切换前核对并保留62个0902任务，活动0。旧正常Runner50776/24080停止，替换发生于任务表SHARE锁窗口，Java不能在该窗口创建/重置任务。首次Start-Process虽成功启动完整新源码，但子进程继承输出句柄使脚本等待；只停止刚启动且空闲的31236/29284后，用关闭继承句柄的隐藏进程重启。最终另一次SHARE锁窗口核对源码完整、全部库存指纹一致并启动验证；两次之间仍无任务或业务数据变化。该基础设施问题及最终启动记录在[cutover.json](cutover.json)，未以半份源码运行，也未重放模型请求。

[guard-after.json](guard-after.json)确认正常配置哈希、全部工程量、全部快照、文件状态/输入修订、任务、执行冻结记录指纹一致；未修改正式或历史成果。001/002/003迁移不重复执行、不删表。003历史数据保留；新普通任务的执行冻结仍必需。

旧task_id换request_id不会解除冻结。已有optimized任务、旧源码指纹任务及本库盘点59个无冻结历史任务不能悄悄使用新源码续跑。新普通任务使用当前完整对象协议。此59项清单仅针对当前库；跨环境、恢复备份或导入历史任务需重新核验任务边界，不具备通用STALE/新run体系。原失败20份没有自动重试，不能通过删冻结记录来强行续跑。

实际测试界面地址：

- 旧20份成功项目：<http://localhost:5173/smartCost/project/manage?projectId=2120051464269168642>，只读核对原成果，预期20/20保留。
- 旧失败试用项目：<http://localhost:5173/smartCost/project/manage?projectId=2120108821166653442>，保留失败任务与文件原状态，不自动重算、不推进0903。

本轮不通过点击下一步/重试来绕过旧任务冻结。新真实模型测试需另有符合当前版本的明确新任务边界和授权范围。

## 5. 独立验收、文档与回退

按用户指定沿用gpt-6.1-terra、xhigh子Agent独立验收，读取源码差分、PG日志、原响应重放和切换保护。其独立结论见[terra-acceptance.md](terra-acceptance.md)；本报告不替代其尚未观察的UI或新真实模型验收。

随后该Agent独立只读核对现有UI，确认旧项目显示“已完成20/20、未处理0”，未点击下一步/重做/重试。界面“全部297、未挂接275”仍为原值：只读DB为306条（主材217、设备80、类型NULL9），原Java列表只显示设备/主材两类，因此9条类型待确认记录不在页面计数中；这是既有展示限制，未在本轮修改，不能把20/20处理完成当成306条全部可见或全部语义正确。

已更新同一权威方案文首及§16、接入细则阶段顺序/§20/§22/§23、README和ADR-0006实施边界。旧171条登记仅给本次25项及5个相关门槛追加撤除证据；旧预期、旧状态和无关项目逐值不变，见[documentation-checks.json](documentation-checks.json)。旧“实现/启用”描述保留为有日期的历史，不再作为当前计划。

本轮回退目标已经落实为普通完整对象串行基线，旧优化不可用开关重新启用。程序故障演练已验证拒绝换版本提交、源变回滚、scope失败整文件不提交、旧成功/人工成果保护；真实多Runner在途回退未跑且实现仍不完整。当前退出/恢复只在任务边界执行；若以后撤回本次代码，先核对无活动任务并停止本次Runner，按完整归档恢复同版本模块集合、原测试和配置合同，复验后才能启动；不能单独复制一个模块、把优化设true或删除数据库冻结来混跑。该“恢复旧源码”操作本轮未执行，不能标为通过，也不是重新启用失败优化的授权。

剩余限制：原有分类/命名及理由数值语义问题不因删除优化自动解决；数值修复候选仍未验收通过/未部署。当前验证证明程序恢复原处理路径并保护已有成果，不能承诺未来20份模型输出必然全部正确。没有新的提速或降本结论。
