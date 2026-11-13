# 单份魏大湾设备表：0902真实运行与快照验收

2026-11-10，北京时间。本次按用户授权启动当前Python Runner，由指定的 **gpt-6.1-terra / xhigh** 子Agent读取阶段产物、在现有界面建立独立测试项目、触发0902并独立验收。业务模型仍为原配置的百炼deepseek-v4.1-flash；两者职责不同。

**工程量与快照保存主路径通过；界面严格展示准确性存在一项非阻断缺陷。** 一份真实设备表经Java解析和3次真实模型请求完成，4条工程量、1条快照及文件2102在同一数据库事务提交。没有进入0903，没有重跑其他料表。测试期间未改生产代码、Prompt或数据库结构。

## 结果

| 原料表对象 | 工程量 | 分类 | 实际结果 |
|---|---:|---|---|
| 单晶双面光伏组件620Wp | 10530块 | 设备1303 | 与原表一致 |
| 组串式逆变器320kW | 16台 | 设备1303 | 与原表一致 |
| 箱变3200KVA | 1台 | 设备1303 | 与原表一致 |
| 箱变2000KVA | 1台 | 设备1303 | 与原表一致 |

箱变总项2台保留为summary，没有独立出表；3条电压/电流属性没有变成实物。8条原始行均保留在快照结构和来源映射中。4条设备均挂到“魏大湾光伏场区 / 电气部分”，未挂接0；界面刷新后数量、分类、CBS和1/1完成状态保持一致。

数据库快照为`6fc0be48-350a-4018-ac01-9195d5cd1e7b`，`input_revision=10`、`result_revision=1`、`snapshot_schema_version=1.0`。正文与当前原文和17列工程量一致，来源和结果指纹通过。JSON紧凑序列化为16,377字节，仅描述本样例正文大小，不代表PostgreSQL物理占用或其他料表大小。

工程量4行、快照行及文件状态行的PostgreSQL `xmin`均为 **70254**。结合正式Runner的save_committed及此前PG故障回滚测试，验证工程量、快照和2102共用文件事务；本轮只执行真实成功路径，未在共享库制造故障。

22项只读数据库检查全部通过。之前4529条工程量和169个文件的状态/输入修订均未变化，所有0903任务与测试前一致。新项目的任务status=1、error_message=NULL。

## 测试定位与交接

- 项目：`TERRA-SNAPSHOT-20261110`，ID `2119987658667032578`。
- [打开测试项目](http://localhost:5173/smartCost/project/manage?projectId=2119987658667032578)。Web5173和Java8080均复用已有进程。
- 批次：`3fc2f160-2664-4929-9e28-d8174a4d9dd7`。
- 唯一0902料表：`a8b023f2-795f-4573-9713-3532e8a056b5`，原文件为`8.魏大湾BD25170-08-EL-EQL设表.doc`。
- 任务：`d1b41d81-926e-4de8-8ad3-f477428a3568`，10:58:48开始，10:58:58完成；没有模型重试。这是单次样例观察，不作性能或准确率承诺。
- 新建项目必填的设计说明使用既有明确标注“合成验收用途”的说明夹具，未调用设计说明AI；0902只处理上述一份设备表。

代码来自SVN r48基线上的工作副本，未提交；17个运行文件的整体SHA-256为`3adb5e1c102de7b7d04606b2e32781eb0eba8e5f3e6b8c94dcae4e400c2563dd`，测试前后完全一致。逐文件版本见[code-version.json](code-version.json)，已有前后端环境及源码指纹见[environment-version.json](environment-version.json)。Java实例未重建，其源码指纹不能单独证明运行字节码版本，真实交接以此次界面/数据库证据为准。

**代码版本、修改文件、启动方式、测试地址、用例和预期统一见[handoff.md](handoff.md)。** 本次新增文件均为验收脚本和证据，上一阶段快照实现文件未修改。

## Runner状态

启动前没有正常Runner进程，因此本次直接启动当前版本，没有结束不存在的旧进程。北京时间10:55:05进入轮询，启动器PID40164，实际Python PID45192；测试后确认仍在运行，按用户意图保留正常0902监听。

工作目录`E:/smartCost/smart-cost-ai`，原启动方式：

```powershell
.venv/Scripts/python.exe -B -X utf8 runner.py --config config.application.local.json --check-config
.venv/Scripts/python.exe -B -X utf8 runner.py --config config.application.local.json
```

当前进程已经运行，无需重复启动。进程及日志位置见[runner-process.json](runner-process.json)。运行配置未修改，仍为backend_queue、仅0902。

## 独立验收与未修复现象

Terra从原DOC文本独立确认四条数量及箱变汇总关系，并对比数据库、源行、完整结构、映射、17列成果和事务ID。实际界面操作及四张截图见[terra-report.md](terra-report.md)。主路径PASS；其中LIVE06的严格显示准确性单列FAIL：两条箱变容量重复显示。

原因证据：当前名称已含`3200KVA/2000KVA`，specification也含该容量；QuantityPanel.vue依次渲染两个字段。旧历史结果也有这两个字段组合，属于既有显示现象，未归因于新增快照；数量、分类和保存值均一致。本轮未改界面代码。

刷新另出现菜单警告“定额关联规则 /system/ruleA06 前端页面未匹配”，未执行0903或改变定额数据，作为独立观察保留。当前样例没有验证成套合并、跨段并发、输入修改竞态或0903消费；这些不能借本次通过宣称已真实验收。逻辑表边界仍明确UNKNOWN，不声称已具备完整A06分组条件。

## 可复核证据

- [before-database.json](before-database.json)、[test-input-before.json](test-input-before.json)：既有成果保护及新测试解析输入。
- [source-reference.json](source-reference.json)：源表历史解析资料；Terra另核对了原DOC文本，没有将旧结果直接当成金标。
- [task-submitted.json](task-submitted.json)、[after-database.json](after-database.json)、[database-checks.json](database-checks.json)：真实任务、保存结果及22项断言。
- [file-trace.jsonl](file-trace.jsonl)、[trace-summary.json](trace-summary.json)、[runner.stderr.log](runner.stderr.log)：3次实际模型请求和唯一提交事件。
- [terra-report.md](terra-report.md)：指定模型与推理级别的独立验收，包含界面截图及保留问题。

测试项目、工程量、快照和证据均保留，供用户复核；没有清空或覆盖原项目成果。
