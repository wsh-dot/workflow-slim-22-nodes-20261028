package com.cq.design.smartcost.modules.project.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * 项目 CBS 引入平台标准结构请求：把勾选的标准明细按层级写入项目 CBS。
 *
 * <p>服务端不信任前端提交的层级关系，只接收「明确勾选的明细 ID 集合」与「级联标志」，
 * 由服务端重新查询平台模板树后计算最终引入的节点集合，并重新生成项目内的父子关系。</p>
 */
@Data
public class ProjectCbsImportInput {
    /** 所属项目 UUID。 */
    @NotBlank(message = "项目ID不能为空")
    private String projectId;

    /**
     * 右侧当前选中的节点 UUID，用于按挂接位置规则推导实际父节点。
     *
     * <p>未选中时挂到项目根节点；选中非叶子节点时挂到该节点下面；
     * 选中叶子节点时挂到该叶子节点的父节点下作为同级节点。</p>
     */
    private String targetNodeId;

    /** 用户明确勾选的平台标准明细 UUID 集合。 */
    @NotEmpty(message = "请先选择要增加的标准结构")
    private List<String> detailIds;

    /**
     * 用户明确取消勾选的平台标准明细 UUID 集合。
     *
     * <p>这些节点及其子树会从最终引入集合中排除，
     * 避免被级联规则重新带出。</p>
     */
    private List<String> excludedDetailIds;

    /**
     * 是否级联。为真时服务端自动关联所选节点的父节点与全部子节点；
     * 为假时只引入明确勾选的节点。
     */
    private Boolean cascade = Boolean.TRUE;
}
