package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

import java.util.List;

/** 项目 CBS 结构操作结果：受影响子树的最新节点视图。 */
@Data
public class ProjectCbsOperationResult {
    /** 所属项目 UUID。 */
    private String projectId;

    /** 本次操作直接影响的节点 UUID 集合。 */
    private List<String> nodeIds;

    /** 操作说明，供前端提示。 */
    private String message;
}
