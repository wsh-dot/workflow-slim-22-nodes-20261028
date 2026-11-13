package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

import java.util.List;

/** 项目 CBS 引入标准结构的结果视图。 */
@Data
public class ProjectCbsImportResult {
    /** 所属项目 UUID。 */
    private String projectId;
    /** 本次写入的顶层节点 UUID 列表。 */
    private List<String> rootIds;
    /** 本次写入的节点总数（含各级下级）。 */
    private int totalCount;
    /** 引入后的项目 CBS 根节点 UUID。 */
    private String cbsRootId;
}
