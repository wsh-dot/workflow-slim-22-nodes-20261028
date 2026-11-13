package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

/** 批次视图：项目最新批次的关键信息，供前端流程步骤条按 current_stage 控制交互。 */
@Data
public class BatchView {
    private String id;
    private Integer batchNo;
    /** 批次状态（字典 08）。 */
    private String status;
    /** 当前组价节点（字典 09，如 0901 CBS编制）。 */
    private String currentStage;
}
