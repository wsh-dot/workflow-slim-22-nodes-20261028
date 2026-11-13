package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/** 项目 CBS 节点树视图，层级由 parent_id 还原。 */
@Data
public class ProjectCbsNodeView {
    /** 节点 UUID。 */
    private String id;
    /** 所属项目 UUID。 */
    private String projectId;
    /** 父节点 UUID，项目根节点为空。 */
    private String parentId;
    /** 项目 CBS 编码。 */
    private String code;
    /** 节点名称。 */
    private String name;
    /** 分类字典编码。 */
    private String categoryCode;
    /** 分类名称快照。 */
    private String categoryName;
    /** 同级排序号。 */
    private Integer sortNo;
    /** 层级路径码。 */
    private String innerCode;
    /** 来源 CBS 模板 UUID。 */
    private String sourceCbsId;
    /** 来源标准 CBS 明细 UUID。 */
    private String sourceCbsDetailId;
    /** 下级节点。 */
    private List<ProjectCbsNodeView> children = new ArrayList<>();
}
