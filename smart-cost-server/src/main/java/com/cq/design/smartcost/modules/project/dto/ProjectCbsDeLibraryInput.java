package com.cq.design.smartcost.modules.project.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

/** 项目 CBS 节点挂载定额库请求。 */
@Data
public class ProjectCbsDeLibraryInput {
    /** 所属项目 UUID。 */
    @NotBlank(message = "项目ID不能为空")
    private String projectId;

    /** 当前项目 CBS 节点 UUID，关联 sc_project_cbs.id。 */
    @NotBlank(message = "请选择要挂载定额库的结构节点")
    private String projectCbsId;

    /** 待挂载的定额库 UUID 集合，关联 sc_de_library.id。 */
    private List<String> deLibraryIds;
}
