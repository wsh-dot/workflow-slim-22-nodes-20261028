package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

/** 项目 CBS 节点已挂载的定额库视图，附定额库编码与名称。 */
@Data
public class ProjectCbsDeLibraryView {
    /** 关联记录 UUID，关联 sc_project_cbs_de_library.id。 */
    private String id;
    /** 所属项目 UUID。 */
    private String projectId;
    /** 当前项目 CBS 节点 UUID。 */
    private String projectCbsId;
    /** 定额库 UUID，关联 sc_de_library.id。 */
    private String deLibraryId;
    /** 定额库编码。 */
    private String deLibraryCode;
    /** 定额库名称。 */
    private String deLibraryName;
    /** 定额库类型字典编码：QUOTA、INDICATOR。 */
    private String deLibraryType;
}
