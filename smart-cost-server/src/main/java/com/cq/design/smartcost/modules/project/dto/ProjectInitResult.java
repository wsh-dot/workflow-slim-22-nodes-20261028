package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

/** 项目初始化结果：默认批次与 CBS 根节点的创建情况。 */
@Data
public class ProjectInitResult {
    /** 项目 UUID。 */
    private String projectId;
    /** 默认批次 UUID。 */
    private String batchId;
    /** 默认批次号。 */
    private Integer batchNo;
    /** CBS 根节点 UUID。 */
    private String cbsRootId;
    /** CBS 根节点名称，取项目名称。 */
    private String cbsRootName;
    /** 本次是否新建了默认批次。 */
    private boolean batchCreated;
    /** 本次是否新建了 CBS 根节点。 */
    private boolean cbsRootCreated;
}
