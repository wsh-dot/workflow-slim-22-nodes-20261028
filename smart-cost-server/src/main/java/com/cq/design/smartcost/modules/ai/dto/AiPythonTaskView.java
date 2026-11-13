package com.cq.design.smartcost.modules.ai.dto;

import lombok.Data;

/** AI 任务视图：前端创建任务与轮询任务状态的返回体。 */
@Data
public class AiPythonTaskView {
    /** 任务 UUID。 */
    private String id;
    /** 任务请求 ID（唯一键）。 */
    private String requestId;
    /** 所属项目 UUID。 */
    private String projectId;
    /** 所属批次 UUID。 */
    private String batchId;
    /** 任务类型：组价节点编码（0901/0902/...）。 */
    private String taskType;
    /** 任务状态：0 执行中、1 已生成（完成）、其他视为失败。 */
    private String status;
    /** 失败或超时原因。 */
    private String errorMessage;
}
