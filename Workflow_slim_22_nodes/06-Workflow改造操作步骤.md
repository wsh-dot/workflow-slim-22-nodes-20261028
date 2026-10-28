# 新建 Java 专用 Workflow：22 节点精简搭建步骤

状态：待实施方案；本次修改的是配置文档，未修改运行中的 Dify、Java 或 AI 服务。旧应用保持原样。

## 1 采用的精简方式

新应用一次运行只处理一份文件；正常仍可在同一次运行看见“结构理解 → CBS 两轮”的主干。批量调度、任务隔离、统一技术失败处理、对账与恢复由已经需要持久任务能力的 AI 服务负责。

核心 22 节点，完整清单和变量绑定见[07](07-Workflow逐节点配置参考.md)。模型节点必须提供完整 text。只有 structured_output 的部署增加 3 个序列化节点成为 25 个；不是所有部署都能直接删这 3 个适配器。

未采用“Dify 仅按 stage 调一个模型、所有正常阶段均由服务分别启动”的更少节点方案，因为这会把正常文件从一次 Dify run 改成三次，并弱化单文件主干的可视化。本次选择保持完整正常业务链，仅把必要纠正与故障恢复分成新的运行。

## 2 先实现服务契约

1. 保留 Java 批量 build、jobs 和单文件 result 三类公开接口。
2. 持久保存 job、file job、单文件 dispatch、真实 workflow_run_id、task_id、dify_user、execution_config_id、workflow_id、阶段 attempt、原始输入和结果。
3. 实现[02 §7](02-接口与节点契约.md)的六个内部 POST：claim、结构提交、CBS 首轮准备与提交、CBS 二轮准备与提交。
4. 所有读写都校验当前派发、实际运行、文件归属、冻结版本和尝试身份；领取与提交用原子条件更新。
5. 所有终态入口复用同一幂等发布函数。合法结构永远可被 CBS 失败恢复引用；没有结构不生成假树。
6. 实现正常结束与异常结束的持久对账器。REPAIR_REQUIRED 为继续状态，最多安排一次纠正；发布待办也由它补齐。

这些接口是拟新增实现。仅删除画布节点、却没有上述服务能力，不属于完成精简。

## 3 建立新应用

1. 只读保存旧 Workflow 的导出基线，新建独立应用、App ID 和 API Key。
2. 设置 QUANTITY_API_BASE、Secret QUANTITY_API_TOKEN、QUANTITY_EXECUTION_CONFIG_ID。AI 服务按冻结配置选择新应用地址、凭据和发布版本，首次执行、纠正及恢复均使用相同配置。
3. Start 只接收单文件 dispatch_id。核对实际 workflow_run_id、workflow_id 的变量绑定，并验证 claim 在版本不符时返回 409。所有内部 HTTP 增加版本头与执行配置头，沿用现有 reader 校验。
4. 不添加 Iteration、迭代开始节点、当前 item 提取节点、批量对账和批量回执节点。

## 4 按阶段连接主干

入口：qStart → qClaimRun → qReadRunState → qResumeGate。

qResumeGate 按服务持久状态选择：

- STRUCTURE_INITIAL 或 STRUCTURE_REPAIR：进入 sLLM。
- CBS_LEAF：进入 qPrepareLeaf。
- CBS_PARENT：进入 qPrepareParent。
- RETURN：进入 qEnd。

结构：sLLM → sProcess → sReadProcess1 → sStructureGate。合法结构转 CBS 首轮准备；需要纠正或已持久化失败则结束本次 run。服务在原运行结束后新建 dispatch，仍绑定同一 file job 与 buildGeneration，纠正输入由 claim 返回。

CBS 首轮：qPrepareLeaf → qReadLeafInput → qLeafInputGate → qCbsLeafLLM → qCbsLeafValidate → qReadLeafValidation → qCbsCandidateGate。有候选转父轮准备，不能继续时服务保存完整结果并结束本次运行。

在首轮提交服务中先检查同名候选 judgment 一致，再筛选候选。冲突时保存完整未挂接结果、CBS_OUTPUT_INCONSISTENT 和原始评价，返回 RETURN；已有 Gate 直接进入 End。Java 使用现有“未挂接”页签及“挂接”按钮，semanticStatus 不因仅 CBS 未匹配改为 REVIEW。

CBS 二轮：qPrepareParent → qReadParentInput → qParentInputGate → qCbsParentLLM → qCbsParentValidate → qReadParentValidation → qEnd。父轮准备有自己的 Gate，不能在容量不足或已形成结果时仍调用模型。

各分支通过控制连线进入同一个 End。End 只引用入口身份，不合并前序分支业务对象，因此不需要 Variable Aggregator 或额外的结果透传节点。

## 5 配置模型提交

三个 LLM 分别绑定原[结构提示词](04-模型-System.md)、[CBS 两轮提示词](05-CBS两轮匹配提示词.md)及对应三个 Schema。

三个提交 HTTP 使用 raw body 直接选择实际模型 text，Content-Type 为 text/plain; charset=utf-8。服务解析并校验完整文本；阶段、输入包、候选、规则和尝试身份由可信服务记录绑定，不由模型填请求外壳。

若插件无完整 text，则在三个模型提交前分别保留 sBuildProcessBody、qBuildLeafBody、qBuildParentBody，将结构化对象安全序列化成完整 JSON 文本。此时全图为 25 节点。不要给整个 JSON 外面再套引号，也不要用模板拼接任意模型字符串。

## 6 配置失败与恢复

HTTP、reader 和 LLM 技术失败直接使本次 run 失败，不在画布内创建另一套失败保存链。服务追踪运行，并对照持久阶段决定回读、重试、继续发布或耗尽终止。

关闭模型节点自动重试，技术尝试由服务有界记录。HTTP 原请求可按幂等身份重传；准备接口重传不能分配第二个 attempt。实际 HTTP 对 4xx/5xx 的行为及变量类型需要部署验证，reader 始终检查业务错误。

CBS 失败但结构已合法时，恢复器重试耗尽发布完整树、空自动挂接目标及明确 CBS 技术失败。不能只删除 failure 节点后把文件丢掉。未知远端运行继续占用资源预算，确认停止后才能重派。

AI 服务固定 streaming 调用，保存实际 SSE 中的 task_id 及原 user。取消使用 `/workflows/tasks/{task_id}/stop`，查询使用 workflow_run_id，停止确认后继续查证真实终态。按 02 §7.4 实现 WORKFLOW_ID 或 IMMUTABLE_APP 版本策略；版本缺失时不自动改跑当前最新版。

## 7 调整并发与 Java 闭环

取消每批4文件、全局2批、批内并发2的旧画布参数。服务以最多4个活跃单文件 run 为实验起点，统一处理多用户公平、共享凭据额度和跨实例协调；不是已验证最优值。

Java 后台按文件取得完整 tree、cbsMatch、rowDispositions、issues 和同一 resultRevision，校验当前版本后事务保存。End 返回身份不是 Java 业务结果。

## 8 验证与发布

依次执行 `python verify_simplified.py`、`python verify_examples.py`、`python verify_regressions.py`，验证静态图、已附合成样例和三项修订反例，再完成[03](03-搭建与验收.md)的真实部署及业务验收。上述脚本不调用 Dify，也不能证明服务实现存在。

仅在目标版本真实运行验证后，按已有授权发布新应用。导出实际 DSL，并核对旧应用的节点、提示词、Key 和发布版本保持原样。
