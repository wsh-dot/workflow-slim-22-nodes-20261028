# 联调合成样例来源

本目录用于本地契约验证。所有规则、身份和接口地址均为示例，不能据此确认企业分类或真实模型质量。

15 份原始 JSON 从本机 `outputs/java-dify-quantity-integration-20261027/examples` 复制，原目录保持不变。它们覆盖 Java 请求、模型结构输出、两轮 CBS 输入输出、完整树、未挂接树和工程节点。

本次增加三份文件：

- `cbs-leaf-output-inconsistent.json`：同名候选产生冲突判断的非法输出。
- `build-result-cbs-inconsistent.json`：对上述非法输出返回完整树与未挂接状态。来源树本身无质量疑点，因此 semanticStatus 保持 READY；CBS 诊断单独记录。
- `runtime-contract.json`：虚构的固定版本调用、实际运行身份、claim 请求头及停止请求。该记录中停止已确认，但终态尚未确认，不能释放未知占用。

`build-result-unmatched.json` 的 REVIEW 来自该样例自身的 PARTIAL 解析，不是单纯未挂接造成。挂接状态统一使用 cbsMatchStatus，值为 0 时由 Java 放入现有“未挂接”页签，不增加挂接待确认状态。

在上级目录执行 `python verify_examples.py` 和 `python verify_regressions.py`。这两项检查不会连接服务或模型。
