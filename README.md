# 工程量 Workflow：22 节点方案阅读入口

本仓库仅包含待实施的 Java 专用 Dify Workflow 方案及本地可交互说明页，不包含已部署的应用。方案版本为 `quantity-workflow-slim-v1.1`，修订日期 2026-10-27。

## 推荐阅读顺序

1. `Workflow_slim_22_nodes/00-精简变更说明.md`：本次修订和状态。
2. `Workflow_slim_22_nodes/01-方案说明.md`：整体业务与架构。
3. `Workflow_slim_22_nodes/02-接口与节点契约.md`：业务字段、接口及服务契约的权威来源。
4. `Workflow_slim_22_nodes/03-搭建与验收.md`：搭建与验收边界。
5. `Workflow_slim_22_nodes/04-模型-System.md`、`05-CBS两轮匹配提示词.md`：三个 LLM 节点的 System 提示词。
6. `Workflow_slim_22_nodes/06-Workflow改造操作步骤.md`、`07-Workflow逐节点配置参考.md`、`08-多用户并发与任务隔离.md`：实际搭建、逐节点配置与服务责任。
7. `Workflow_slim_22_nodes/workflow-node-inventory.json`：22 个核心节点与 28 条业务连线。
8. `Workflow_slim_22_nodes/*schema.json`、`examples/`、验证脚本与结果：输出契约、合成样例及本地检查范围。
9. `Workflow_slim_22_nodes_visual/index.html`：下载后在浏览器本地打开；该文件自包含，不能代替方案与契约。其补写 reader 代码、示意响应和提议字段均须部署验证。

`给Gemini的提示词.md` 是可复制给 Gemini 的完整阅读与讲解任务。examples 中的身份、规则及接口地址均为合成示例；不能据此宣称企业业务、真实模型或 Dify 联调已经验收通过。

当前仓库为公开仓库。Gemini 是否能完整读取文件仍取决于其网页访问能力和上下文限制。若无法读取或只能看到部分文件，请将仓库打包上传，或通过可用的连接提供文件。
