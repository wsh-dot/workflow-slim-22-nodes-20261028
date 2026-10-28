# Java 专用 Workflow 逐节点配置参考：22 个核心节点

本文是精简后的待实施配置方案。现有 Workflow 原样保留，另建独立的 Java 专用 Workflow，使用独立 App ID、API Key、草稿和发布版本。本文中的增删与调整只针对新应用，不修改旧应用。

本版采用单文件执行：一次 dispatch 只处理一个 file job。正常文件在一次 Workflow 运行中依次完成结构理解、CBS 单位工程名称匹配、CBS 直接父节点名称匹配。结构需要纠正时，AI 服务在本次运行结束后创建新的 dispatch，继续同一个 file job，最多纠正一次。批量排队、共享并发、运行追踪、恢复与对账由 AI 服务承担。

**核心画布为 22 个逻辑节点：3 个 LLM、6 个 HTTP、6 个 Code reader、5 个 Gate、Start 和 End 各 1 个。** 若目标部署只能提供 `structured_output`，则为三个模型分别增加一个序列化 Code，共 25 个逻辑节点。22 和 25 都是配置设计数量，不是已经导入、发布或验证通过的运行结果。本文不是可直接导入的原生 DSL。

业务字段以 [接口与节点契约](02-接口与节点契约.md)为准，画布步骤见 [Workflow 操作步骤](06-Workflow改造操作步骤.md)，调度与隔离见 [多用户并发与任务隔离](08-多用户并发与任务隔离.md)。本次精简不改变三份模型 Schema、行角色、企业设备材料分类规则或两轮 CBS 的业务判断顺序。

## 1 公共配置与执行边界

| 配置项 | 本版约定 |
|---|---|
| 应用隔离 | 新建 Java 专用 Workflow；旧应用节点、连线、提示词、环境变量及发布版本保持原样 |
| 应用调用 | AI 服务按冻结 execution_config_id 选择新应用地址、凭据及 workflow_id；固定版本模式或不可变应用模式见 02 §7.4，response_mode 固定 streaming |
| `QUANTITY_API_BASE` | Dify string 环境变量，AI 服务基址，不含末尾斜杠 |
| `QUANTITY_API_TOKEN` | Dify Secret 环境变量，仅用于服务认证 |
| `QUANTITY_EXECUTION_CONFIG_ID` | 新应用静态 string 环境变量，标识冻结的执行配置；存在原任务时不原地改值 |
| HTTP 认证 | Bearer，绑定 `QUANTITY_API_TOKEN`；内置认证与手工 Authorization 头二选一 |
| 所有内部 HTTP 的派发头 | `X-Quantity-Dispatch-Id` 绑定 `qStart.dispatch_id` |
| 所有内部 HTTP 的运行头 | `X-Quantity-Run-Id` 绑定当前 Dify 实际运行 ID；实际系统变量名称及可用性必须在目标部署核对 |
| 所有内部 HTTP 的版本头 | `X-Quantity-Workflow-Id` 绑定实际版本变量，核对目标部署的 `sys.workflow_id`；不得填写 workflow_run_id |
| 所有内部 HTTP 的配置头 | `X-Quantity-Execution-Config-Id` 绑定 `env.QUANTITY_EXECUTION_CONFIG_ID`；服务与 dispatch 冻结配置核对 |
| 运行登记及取消 | AI 服务持久保存实际 task_id、workflow_run_id、workflow_id、dify_user 和应用配置身份；停止用 task_id，查询用 workflow_run_id，不能互换 |
| 模型提交的尝试头 | `X-Quantity-Attempt-Id` 绑定该阶段 reader 返回的服务端 `attempt_id`；不得让模型填写 |
| 模型提交的正文 | `Content-Type: text/plain; charset=utf-8`；raw body 直接绑定对应 LLM 的完整 `text`，不再包一层 JSON，不手工转义 |
| claim、prepare 的正文 | 使用 `Content-Type: application/json` 和空对象 `{}`；阶段与身份由 URL、可信请求头及服务记录确定 |
| HTTP 初始超时 | connect 10 秒、read 60 秒、write 30 秒；仅为待验证初值 |
| HTTP 初始重试 | 最多额外重试 1 次、间隔 1 秒；保持相同 URL、请求头与原始正文，服务必须幂等 |
| LLM 自动重试 | 关闭节点自动重试；语义纠正与技术重试由服务分别计数 |
| Code | Python 3，仅解析响应、校验身份及输出浅层变量；不访问网络、文件或数据库 |
| 节点异常 | 不配置默认成功值；技术异常让本次 run 失败，由 AI 服务回读持久阶段并有界恢复 |
| 文件并发 | 画布中没有 Iteration；每次运行只有一份文件 |
| 全局运行初值 | 全服务合计最多 4 个活跃单文件 run；共享原子许可，未经压测，不是平台吞吐承诺 |
| 失联占用 | 未确认停止的旧 run 继续占许可，不能因租约 TTL 到期立即释放并重派 |
| 模型总限流 | 其他应用共享模型凭据时，一并控制模型并发、请求数及 Token 配额 |
| API user | AI 服务按可信租户和提交者生成稳定标识，并保存实际调用值 |

HTTP 节点的认证、请求体、超时、重试和异常行为应按目标部署检查。[Dify HTTP Request](https://docs.dify.ai/en/cloud/use-dify/nodes/http-request)

**真实 run ID 是领取与防止重复执行的必要身份。** 不得用 dispatch ID、随机数或空值冒充。若当前部署不能在首个 HTTP 节点可靠提供实际 run ID，本版 claim 契约尚不能完成配置，应先解决可信运行关联，再联调；不能省略绑定后声称已经具备重复执行隔离。

正文中的节点名称是逻辑 ID。变量须使用当前新应用的变量选择器绑定，不直接复制其他应用的内部 ID。`S` 表示 string，`N` 表示 number；所有路由字段均为枚举字符串。

## 2 为什么能够精简

本版删除的是画布中的重复编排和包装节点，以下职责继续保留。

| 原画布职责 | 精简后的归属 |
|---|---|
| 一次运行内按文件 Iteration | AI 服务逐文件派发、排队和公平调度 |
| 独立的第二套结构模型、提交与校验链 | 服务保存纠正计划，新 dispatch 以 `STRUCTURE_REPAIR` 入口复用同一条结构链 |
| 首轮与纠正的结构引用汇合 | CBS 准备接口回读当前合法结构，不从可能未执行的分支取变量 |
| 多个只传结果引用的 Code 与 Variable Aggregator | 业务阶段接口持久化状态；各返回分支进入同一个只输出身份的 End |
| CBS 结果汇合、独立 finalize 与文件信封 | CBS 阶段接口负责校验、生成完整树和发布不可变文件结果 |
| 多条结构/CBS 失败保存链 | 服务端阶段记录、运行追踪及有界恢复器 |
| 迭代输出、批量 reconcile 和派发摘要包装 | AI 服务按预期 file job 清单与持久状态对账 |

行覆盖、父子引用、数量来源、企业分类依据、候选覆盖、相同匹配证据、唯一目标以及完整树校验均不能删除。仅仅减少 Dify 节点而未实现这些服务职责，不算完成精简方案。

## 3 内部接口与持久阶段契约

### 3.1 统一响应与元数据

成功响应使用 `{"status":"1","data":{...}}`，错误响应使用 `status="0"` 和明确错误。reader 先检查 HTTP 状态、JSON 可解析性、status、当前 dispatch、实际 run 和文件身份，再读取 data。不得假设 HTTP body 已经是对象，也不得直接绑定 `body.data`。

reader 正常返回时必须包含全部已声明输出；当前 RETURN 分支不使用的输入字符串、attempt 或上下文字段显式转换为空字符串。未知动作、非法身份及缺少该动作必需的数据直接抛错，不返回默认成功对象。HTTP 节点即使将 4xx/5xx 作为普通 body 输出，后续 reader 也必须拒绝该响应。

下面列出的返回字段均位于 data 内。服务响应应回显 `dispatch_id`、`workflow_run_id`、`workflow_id`、`execution_config_id`、`file_job_id`、`file_id`；reader 与入口身份逐一核对。入口 reader 对照实际版本变量及静态配置变量，后续 reader 对照入口已验证值。输入、规则、CBS 快照、提示词/Schema 版本和模型配置属于服务冻结的阶段快照，`attempt_id` 引用这一份快照。packet ID 和 context ID 必须与对应快照一致。版本不符返回 409 EXECUTION_VERSION_MISMATCH，reader 终止本次运行。

| 接口 | 请求 | 返回关键字段与持久化职责 |
|---|---|---|
| POST `/internal/quantity/dispatches/{dispatch_id}/claim` | URL dispatch；真实 run 请求头；body `{}` | 身份、`entry_phase`、`input_json`、`attempt_id`、`packet_id`、`context_id`；原子绑定 dispatch 与实际 run，领取当前阶段 |
| POST `/internal/quantity/files/{file_job_id}/process-text` | 结构模型完整文本；派发、run、attempt 请求头 | 身份、`packet_id`、`next_action`、`stage_status`、`structure_result_ref`、必要结果引用、issues；保存合法结构、纠正计划或无结构失败终态 |
| POST `/internal/quantity/files/{file_job_id}/cbs-leaf/prepare` | 当前身份；body `{}` | 身份、`next_action`、`input_json`、`attempt_id`、`context_id`、必要结果引用；回读合法结构，准备首轮，或持久化未挂接/容量等结果 |
| POST `/internal/quantity/files/{file_job_id}/cbs-leaf/text` | 首轮模型完整文本；派发、run、attempt 请求头 | 身份、`next_action`、`context_id`、`stage_status`、必要结果引用；校验候选并保存父轮准备状态，或发布未挂接结果 |
| POST `/internal/quantity/files/{file_job_id}/cbs-parent/prepare` | 当前身份；body `{}` | 身份、`next_action`、`input_json`、`attempt_id`、`context_id`、必要结果引用；回读同一匹配证据和保留候选，准备父轮或发布保树结果 |
| POST `/internal/quantity/files/{file_job_id}/cbs-parent/text` | 父轮模型完整文本；派发、run、attempt 请求头 | 身份、`next_action=RETURN`、`context_id`、`file_result_ref`、`result_revision`、文件状态；完成父轮校验及完整文件结果发布 |

claim 与 prepare 有持久化副作用，因此使用 POST，并定义幂等行为。claim/prepare 不绑定尚未取得的 attempt；由它们分配或返回该阶段已有的尝试身份。三个模型提交接口才使用 reader 返回的 `X-Quantity-Attempt-Id`。

服务接收模型文本后保存可取得的完整原文，严格解析 JSON，应用原 Schema，再执行业务校验。传输改成文本不意味着取消结构化输出或放宽校验；不能从截断文本中截取部分 rows 或候选后继续成功路径。

### 3.2 入口与动作枚举

`claim.entry_phase` 只允许以下值。

| entry_phase | 含义 | 画布入口 |
|---|---|---|
| `STRUCTURE_INITIAL` | 尚未完成结构首轮 | `sLLM` |
| `STRUCTURE_REPAIR` | 已持久化的一次纠正计划 | `sLLM` |
| `CBS_LEAF` | 已有合法结构，CBS 首轮尚未完成 | `qPrepareLeaf` |
| `CBS_PARENT` | 首轮已完成，只继续父轮 | `qPrepareParent` |
| `RETURN` | 本次 dispatch 无需继续模型执行 | `qEnd`；服务仍回读其实际状态 |

`process-text.next_action` 只允许 `CBS_LEAF`、`RETURN`。`CBS_LEAF` 必须有合法、已保存的结构结果。`RETURN` 可以表示已保存的结构失败终态，也可以表示 `stage_status=REPAIR_REQUIRED`；后者不是文件终态。

`cbs-leaf/prepare.next_action` 只允许 `RUN_LEAF`、`RETURN`。`cbs-leaf/text.next_action` 只允许 `CBS_PARENT`、`RETURN`。`cbs-parent/prepare.next_action` 只允许 `RUN_PARENT`、`RETURN`。`cbs-parent/text` 成功返回时只能为 `RETURN`，且必须已有可回读的不可变文件结果。

**RETURN 只表示结束本次 Dify 编排，不统一表示业务成功或文件完成。** AI 服务根据持久阶段判断继续派发、回读结果或结束任务。各接口的 reader 必须检查具体动作的前置条件，不接受“status=1 但缺少已保存结构、纠正计划或结果”的空响应。

### 3.3 claim、attempt 与重复执行

1. claim 原子校验当前 dispatch 是否有效、属于哪一个 file job、是否已有实际 run 领取，以及该文件是否仍由当前派发持有执行权。
2. 同一实际 run 的网络重传返回原领取结果；不同 run 不得同时领取同一个 dispatch。重复发起 Dify 不能被当作第二次合法执行。
3. 已失效 dispatch 的迟到请求被拒绝。换新 dispatch 前先确认旧 run 已停止，或进入明确的隔离与运行查证流程；不能只按 TTL 重新派发。
4. 服务为每次允许的模型执行冻结 attempt。相同 attempt 的同一正文重传返回原结果；不同正文返回 409。HTTP 重试不能增加语义纠正次数。
5. 只有服务确认需要一次新的技术执行时才分配新的尝试身份；语义纠正次数、技术尝试次数分别持久化且有上限。
6. 已成功的模型阶段使用保存的 checkpoint，不再次调用模型来重新生成同一阶段内容。最终结果已发布时回读原版本，不按旧 attempt 改写终态。

## 4 入口与阶段恢复：4 个节点

| 节点及类型 | 输入绑定 | 输出声明 | 配置与下一步 |
|---|---|---|---|
| `qStart` · Start | API `inputs.dispatch_id` | `dispatch_id:S` | 必填短文本；接 `qClaimRun` |
| `qClaimRun` · HTTP | `qStart.dispatch_id`；当前实际 run ID | `body:S`、`status_code:N` | POST `{{#env.QUANTITY_API_BASE#}}/internal/quantity/dispatches/{{#qStart.dispatch_id#}}/claim`；body `{}`；接 `qReadRunState` |
| `qReadRunState` · Code | body/status_code 来自 `qClaimRun`；预期 dispatch 来自 Start；实际 run/版本变量；env.QUANTITY_EXECUTION_CONFIG_ID | `file_job_id:S`、`file_id:S`、`workflow_id:S`、`execution_config_id:S`、`entry_phase:S`、`input_json:S`、`attempt_id:S`、`packet_id:S`、`context_id:S` | 检查领取身份、实际版本、冻结配置、阶段枚举及阶段输入；接 `qResumeGate` |
| `qResumeGate` · If-Else | `qReadRunState.entry_phase` | 分支 | 两个 STRUCTURE 阶段 → `sLLM`；CBS_LEAF → `qPrepareLeaf`；CBS_PARENT → `qPrepareParent`；RETURN → `qEnd` |

`qReadRunState` 必须在 Gate 之前拒绝未知阶段。结构阶段要求完整 `input_json`、非空 attempt 和 packet；其他阶段不使用结构输入，但 reader 仍返回全部已声明字段，未使用的字符串显式设为空字符串。不得引用尚未执行的后续节点来补入口字段。

`STRUCTURE_REPAIR.input_json` 由服务从冻结快照生成，包含完整原输入、首轮提案及具体错误。它不是再次发送未经修正的首轮输入。

## 5 结构理解与一次纠正：4 个节点

| 节点及类型 | 输入绑定 | 输出声明 | 配置与下一步 |
|---|---|---|---|
| `sLLM` · LLM | User=`qReadRunState.input_json` | 完整 `text:S`；structured_output 按部署实际暴露 | System 使用 [结构提示词](04-模型-System.md)正文；Schema 使用 [结构 Schema](model-output.schema.json)；接 `sProcess` |
| `sProcess` · HTTP | raw body=`sLLM.text`；attempt=`qReadRunState.attempt_id`；file job=`qReadRunState.file_job_id` | `body:S`、`status_code:N` | POST `.../internal/quantity/files/{{#qReadRunState.file_job_id#}}/process-text`；接 `sReadProcess1` |
| `sReadProcess1` · Code | body/status_code 来自 `sProcess`；预期身份、阶段与 packet 来自 `qReadRunState` | `route:S` | 校验 `CBS_LEAF/RETURN`；检查 ACCEPT 有合法结构，REPAIR_REQUIRED 有已保存的一次纠正计划；接 `sStructureGate` |
| `sStructureGate` · If-Else | `sReadProcess1.route` | 分支 | CBS_LEAF → `qPrepareLeaf`；RETURN → `qEnd` |

服务按行覆盖、父子关系、引用、类型、数量来源及工程节点规则校验。`project` 最终映射为 PROJECT，实物分类按企业规则处理；不能因节点减少而退回旧关键词分类或让模型直接生成最终树。

需要纠正时，process 先持久化 `REPAIR_REQUIRED` 及纠正输入，再返回 `next_action=RETURN`。本次 run 正常结束后，AI 服务主动为同一个 file job、同一个 buildGeneration 创建新的 dispatch，以 `STRUCTURE_REPAIR` 进入 `sLLM`。最多一次；纠正后再次不合法不得再登记第三次语义调用。

正常文件只有一次 run、三次模型调用。发生一次结构纠正时，首个 run 完成首轮结构，第二个 run 执行纠正及后续 CBS，两次 run 合计四次模型调用。网络故障下的有界技术尝试另行记录，不能混同为语义纠正额度。

## 6 CBS 首轮准备、匹配与校验：7 个节点

| 节点及类型 | 输入绑定 | 输出声明 | 配置与下一步 |
|---|---|---|---|
| `qPrepareLeaf` · HTTP | file job=`qReadRunState.file_job_id`；当前派发及 run | `body:S`、`status_code:N` | POST `.../internal/quantity/files/{{#qReadRunState.file_job_id#}}/cbs-leaf/prepare`；body `{}`；接 `qReadLeafInput` |
| `qReadLeafInput` · Code | body/status_code 来自 `qPrepareLeaf`；预期身份来自入口 | `route:S`、`input_json:S`、`attempt_id:S`、`context_id:S` | 校验 RUN_LEAF 所需输入、尝试及上下文；RETURN 时检查服务已保存相应结果；接 `qLeafInputGate` |
| `qLeafInputGate` · If-Else | `qReadLeafInput.route` | 分支 | RUN_LEAF → `qCbsLeafLLM`；RETURN → `qEnd` |
| `qCbsLeafLLM` · LLM | User=`qReadLeafInput.input_json` | 完整 `text:S` | [CBS 提示词](05-CBS两轮匹配提示词.md)第一轮 System；[首轮 Schema](cbs-leaf-output.schema.json)；接 `qCbsLeafValidate` |
| `qCbsLeafValidate` · HTTP | raw body=`qCbsLeafLLM.text`；attempt=`qReadLeafInput.attempt_id` | `body:S`、`status_code:N` | POST `.../internal/quantity/files/{{#qReadRunState.file_job_id#}}/cbs-leaf/text`；接 `qReadLeafValidation` |
| `qReadLeafValidation` · Code | body/status_code 来自 `qCbsLeafValidate`；预期身份来自入口；context=`qReadLeafInput.context_id` | `route:S` | 校验 CBS_PARENT/RETURN；检查首轮 checkpoint 或完整文件结果已保存；接 `qCbsCandidateGate` |
| `qCbsCandidateGate` · If-Else | `qReadLeafValidation.route` | 分支 | CBS_PARENT → `qPrepareParent`；RETURN → `qEnd` |

首轮仍使用完整表头、专业、全部内部章节名称和全部合法单位工程候选，不按父节点名称预筛，不做固定 Top-K 截断。相同名称、不同 ID 均保留，服务在筛选前按 leaf_name.strip() 校验 judgment 一致。校验通过才保存 match 与 possible 候选；有保留候选就执行父轮，即使只有一个。

同名判断冲突时，`qCbsLeafValidate` 对应接口发布完整树及 CBS_OUTPUT_INCONSISTENT 未挂接结果，返回 next_action=RETURN、stage_status=OUTPUT_REJECTED 和结果引用。`qReadLeafValidation` 检查结果引用及修订非空、身份一致，再走现有 qCbsCandidateGate 的 RETURN 分支。不新增节点，不把此分支算作首轮成功或无匹配，不自动启动 CBS 重试。完整状态见 02 §5.3。

没有合法候选、没有保留候选或容量无法容纳全量比较时，由对应准备/校验接口保存明确 CBS 原因，并使用已保存合法结构生成完整文件结果。已存在合法结构时，CBS 容量超限形成未挂接，semanticStatus 沿用来源树质量；结构输入在模型调用前已超限、尚无合法结构时则按无结果处理，不用空树伪装 REVIEW 完整结果。

## 7 CBS 父轮准备、匹配与发布：6 个节点

| 节点及类型 | 输入绑定 | 输出声明 | 配置与下一步 |
|---|---|---|---|
| `qPrepareParent` · HTTP | file job=`qReadRunState.file_job_id`；当前派发及 run | `body:S`、`status_code:N` | POST `.../internal/quantity/files/{{#qReadRunState.file_job_id#}}/cbs-parent/prepare`；body `{}`；接 `qReadParentInput` |
| `qReadParentInput` · Code | body/status_code 来自 `qPrepareParent`；预期身份来自入口 | `route:S`、`input_json:S`、`attempt_id:S`、`context_id:S` | 校验 RUN_PARENT/RETURN；RUN_PARENT 必须有完整父轮输入；接 `qParentInputGate` |
| `qParentInputGate` · If-Else | `qReadParentInput.route` | 分支 | RUN_PARENT → `qCbsParentLLM`；RETURN → `qEnd` |
| `qCbsParentLLM` · LLM | User=`qReadParentInput.input_json` | 完整 `text:S` | [CBS 提示词](05-CBS两轮匹配提示词.md)第二轮 System；[父轮 Schema](cbs-parent-output.schema.json)；接 `qCbsParentValidate` |
| `qCbsParentValidate` · HTTP | raw body=`qCbsParentLLM.text`；attempt=`qReadParentInput.attempt_id` | `body:S`、`status_code:N` | POST `.../internal/quantity/files/{{#qReadRunState.file_job_id#}}/cbs-parent/text`；校验并发布完整文件结果；接 `qReadParentValidation` |
| `qReadParentValidation` · Code | body/status_code 来自 `qCbsParentValidate`；预期身份来自入口；context=`qReadParentInput.context_id` | `route:S` | 只接受 RETURN；检查非空 file_result_ref、result_revision 与当前文件身份；接 `qEnd` |

`qPrepareParent` 从服务回读首轮 checkpoint 和原始快照，不引用 `qReadLeafValidation` 的输出。这样，无论正常路径还是直接恢复 CBS_PARENT，都不会读取未执行节点的变量。

第二轮仍使用与第一轮内容和摘要完全一致的 `match_context`，比较第一轮候选各自的直接父节点名称；不换成场区摘要，不新增候选，不把父节点作为最终挂接目标。目标唯一性、候选覆盖及父子映射由服务校验。

父轮准备可能因父节点缺失、容量或已有终态而不再调用模型，因此本版保留 `qParentInputGate`。RETURN 前，服务须保存相应结果；不能向模型发送空输入后期待失败兜底。

父轮提交成功时，服务完成原 finalize 的职责：回读合法结构及原始来源，生成带 children 的完整树、文件级 cbsMatch、rowDispositions 和 issues，持久化不可变 resultRevision，再返回结果引用。不能先返回成功，再异步补生成树。

## 8 单一 End 与服务回读

| 节点及类型 | 输入绑定 | 输出 |
|---|---|---|
| `qEnd` · End/Output | dispatch=`qStart.dispatch_id`；file job=`qReadRunState.file_job_id` | `dispatch_id:S`、`file_job_id:S` |

所有业务 RETURN 分支都直接连接同一个 `qEnd`。End 只引用入口必定已经取得的身份，不读取结构、首轮或父轮的分支输出，不需要终态 Variable Aggregator。

AI 服务每次收到正常 End、运行失败、连接中断或运行状态更新后，都回读持久阶段：REPAIR_REQUIRED 主动续派一次纠正；已完成的阶段不重跑；已有结果回读原版本；尚需技术恢复的阶段按有限次数处理。不能把 End 返回的两项身份解释为“文件已成功完成”。

Java 仍通过 `GET /smartCost/ai/quantity/jobs/{jobId}/files/{fileId}/result` 取得实际完整 JSON。该接口返回 tree、cbsMatch、rowDispositions、issues 及版本信息，不以 Dify 回执、URL、日志或自然语言摘要替代业务数据。

## 9 技术失败、checkpoint 与保树

本版不再为每个 HTTP、Code 或 LLM 配置一套通用失败保存分支。技术异常直接让当前 run 失败；外部服务在所有运行终态上统一查证。业务上的未匹配、输入不可执行和纠正计划仍由阶段接口明确持久化，不能只存在于 Dify 日志。

| 故障位置或状态 | AI 服务必须采取的动作 |
|---|---|
| claim 失败、重复 run 领取 | 拒绝重复执行；回读当前持有者及已有阶段；不能再开一个文件执行许可 |
| HTTP 非成功、响应损坏、reader 身份/动作校验失败 | run 失败；先查接口是否已提交成功，不把响应丢失直接解释为业务未保存 |
| 结构模型技术失败 | 没有合法结构时有界处理；耗尽后形成 FAILED/UNAVAILABLE，不生成半棵树 |
| 首轮结构业务可纠正 | 先保存纠正计划，再 RETURN；正常 run 结束后调度一次 STRUCTURE_REPAIR |
| 纠正后结构仍不合法 | 保存明确失败终态，不再调用第三次语义纠正 |
| CBS 模型或校验技术失败 | 保留合法结构及已成功 CBS checkpoint；仅恢复未完成阶段 |
| CBS 技术尝试耗尽 | 发布完整来源树、未挂接和 CBS 技术失败原因，semanticStatus 沿用来源树质量；不能把技术失败写成语义 no_match |
| 文件结果已保存但响应丢失 | 返回/读取原结果，不再生成新节点，不用迟到失败覆盖成功 |
| Dify 中途结束，未走 End | 服务仍按实际 run 与预期 file job 对账，不依赖一个一定执行的结束节点 |
| 旧 run 是否已停不明确 | 保持许可占用并查证，禁止因 TTL 到期无条件释放并重派 |

成功 checkpoint 和文件发布职责不能删除。首轮结构、一次纠正、CBS 首轮、CBS 父轮分别保存执行身份、输入快照、输出原文或可得输出、校验结果及尝试记录。阶段判定与状态更新使用事务或等效并发控制。

文件终态发布后按不可变结果处理。本版不默认允许同一 file job 的已发布文件结果在后台悄悄升级。需要再次构建时使用明确的新构建意图与 buildGeneration；如未来要求同代次结果升级，需另行定义当前有效 resultRevision 及 Java 原子版本检查，不能用固定 finalize 键提交不同结果。

## 10 22 节点的文本提交前提与 25 节点备选

### 10.1 必须验证的文本能力

三个 LLM 节点继续启用原 JSON Schema。22 节点版本只在目标部署确实暴露完整 `text` 时采用：应检查它包含本次完整 JSON 输出，没有被截断、没有丢字段，也不是错误摘要。Code、HTTP、模型上下文和输出容量都需核对，不能仅因最终树已移到服务就忽略字符串长度限制。

模型和插件的结构化输出能力应按实际版本验证，不假设所有供应商暴露相同变量。[Dify LLM](https://docs.dify.ai/en/cloud/use-dify/nodes/llm) Code 的输出限制也应按部署检查。[Dify Code](https://docs.dify.ai/en/cloud/use-dify/nodes/code)

三个提交节点的 raw body 仅绑定模型文本变量。不要写成 `"{{模型.text}}"`，不要用字符串拼接构造包含模型文本的 JSON 包装，也不要在正文里混入派发、用户、packet 或 attempt 元数据。这些身份来自服务记录和可信请求头。

### 10.2 只有 structured_output 时增加三个 Code

如果部署不能取得完整 text，但能取得完整 `structured_output`，在相应 LLM 与 HTTP 之间分别增加以下节点。

| 可选节点 | 位置 | 输入与输出 |
|---|---|---|
| `sBuildProcessBody` | `sLLM → sProcess` 之间 | 输入实际 structured_output；输出 `request_text:S` |
| `qBuildLeafBody` | `qCbsLeafLLM → qCbsLeafValidate` 之间 | 同上 |
| `qBuildParentBody` | `qCbsParentLLM → qCbsParentValidate` 之间 | 同上 |

HTTP 的 Content-Type 和接口保持文本契约，只把 raw body 改绑为该 Code 的 `request_text`。三个可选节点合计使画布成为 25 节点；不要同时保留已经不使用的旧请求包装版本。

```python
import json

def main(model_output: dict) -> dict:
    if not isinstance(model_output, dict) or not model_output:
        raise ValueError("Missing complete structured model output")
    return {
        "request_text": json.dumps(
            model_output, ensure_ascii=False, separators=(",", ":")
        )
    }
```

序列化器只把实际结构化对象变成完整 JSON 文本，不能补造缺失行或替代服务校验。服务在冻结的执行配置中记录该输出来自 structured_output 序列化；无法取得模型原始文本时明确记为不可得，不能声称序列化结果是逐字原始输出。

若 text 与完整 structured_output 均不可得，则该模型/插件不满足本方案的提交前提；不能提交空对象并继续成功路径。

## 11 完整节点清单与业务连线

### 11.1 22 个核心节点

| 类别 | 逻辑节点 | 数量 |
|---|---|---:|
| Start/End | qStart、qEnd | 2 |
| HTTP | qClaimRun、sProcess、qPrepareLeaf、qCbsLeafValidate、qPrepareParent、qCbsParentValidate | 6 |
| Code reader | qReadRunState、sReadProcess1、qReadLeafInput、qReadLeafValidation、qReadParentInput、qReadParentValidation | 6 |
| Gate | qResumeGate、sStructureGate、qLeafInputGate、qCbsCandidateGate、qParentInputGate | 5 |
| LLM | sLLM、qCbsLeafLLM、qCbsParentLLM | 3 |
| 合计 | 不含三个可选序列化 Code | **22** |

### 11.2 正常与业务分支边

| 起点 | 条件 | 终点 |
|---|---|---|
| qStart | normal | qClaimRun |
| qClaimRun | normal | qReadRunState |
| qReadRunState | normal | qResumeGate |
| qResumeGate | STRUCTURE_INITIAL 或 STRUCTURE_REPAIR | sLLM |
| qResumeGate | CBS_LEAF | qPrepareLeaf |
| qResumeGate | CBS_PARENT | qPrepareParent |
| qResumeGate | RETURN | qEnd |
| sLLM | normal | sProcess |
| sProcess | normal | sReadProcess1 |
| sReadProcess1 | normal | sStructureGate |
| sStructureGate | CBS_LEAF | qPrepareLeaf |
| sStructureGate | RETURN | qEnd |
| qPrepareLeaf | normal | qReadLeafInput |
| qReadLeafInput | normal | qLeafInputGate |
| qLeafInputGate | RUN_LEAF | qCbsLeafLLM |
| qLeafInputGate | RETURN | qEnd |
| qCbsLeafLLM | normal | qCbsLeafValidate |
| qCbsLeafValidate | normal | qReadLeafValidation |
| qReadLeafValidation | normal | qCbsCandidateGate |
| qCbsCandidateGate | CBS_PARENT | qPrepareParent |
| qCbsCandidateGate | RETURN | qEnd |
| qPrepareParent | normal | qReadParentInput |
| qReadParentInput | normal | qParentInputGate |
| qParentInputGate | RUN_PARENT | qCbsParentLLM |
| qParentInputGate | RETURN | qEnd |
| qCbsParentLLM | normal | qCbsParentValidate |
| qCbsParentValidate | normal | qReadParentValidation |
| qReadParentValidation | 已验证 RETURN | qEnd |

本表共 28 条正常及业务分支关系；错误由 run 失败和服务恢复处理，不另增假想的 Gate 原生异常边。Gate 的兜底出口仅处理 reader 已验证的 RETURN，不能用 else 吞掉未知动作。实际导出 DSL 仍需检查其变量选择器、分支 handle 和控制汇合行为。

## 12 实施与验收要求

1. 先实现 claim、阶段 checkpoint、结果发布及共享调度接口，再搭新画布；所有路由都是拟实施路由，不能仅替换 URL 就视为已有能力。
2. 在目标部署确认真实 run ID、实际 workflow_id、streaming 返回的 task_id、版本固定策略、完整 LLM text、三个 Schema、HTTP raw body、状态码处理与 Code 字符串容量。执行配置或实际版本不一致时，claim 必须在模型调用前拒绝。
3. 用固定完整 JSON 先验证正常三阶段、一次结构纠正、首轮无候选、父轮准备 RETURN、未挂接保树及 Java 实际取回完整结果。
4. 验证同 dispatch 不同 run 只能有一个领取成功；同 attempt 同正文返回原结果，不同正文返回冲突；响应丢失先回读保存状态。
5. 验证首轮已成功后恢复父轮时不重复执行结构或首轮；REPAIR_REQUIRED 在正常 run 结束后主动续派，而不是永久停留在等待状态。
6. 验证 CBS 技术重试耗尽仍返回合法完整树；没有合法结构时形成明确失败，不返回半树或默认成功对象。
7. 验证多个服务实例合计仍最多 4 个活跃单文件 run，未停止的旧 run 不释放许可；该数值仍需真实模型额度与料表压测确认。
8. 验证新旧应用配置隔离，旧应用保持原状；记录新应用版本、实际 run、file job、阶段尝试、结果版本及 Java 收到的完整响应。

以上是后续实施与验收要求。本文件没有声称已经搭建或发布画布，没有声称内部服务、真实模型、并发控制或 Java 联调已经验证通过。
