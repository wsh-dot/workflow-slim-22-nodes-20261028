package com.cq.design.smartcost.modules.project.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/** 项目 CBS 节点新增/修改请求输入。 */
@Data
public class ProjectCbsNodeInput {
    /**
     * 右侧当前选中的节点 UUID，用于按挂接位置规则推导实际父节点。
     *
     * <p>未选中时挂到项目根节点；选中非叶子节点时挂到该节点下面；
     * 选中叶子节点时挂到该叶子节点的父节点下作为同级节点。</p>
     */
    private String targetNodeId;

    /** 节点名称。 */
    @NotBlank(message = "节点名称不能为空")
    @Size(max = 200, message = "节点名称长度不能超过 200")
    private String name;

    /** 分类字典编码。 */
    @Size(max = 32, message = "分类编码长度不能超过 32")
    private String categoryCode;

    /** 分类名称。 */
    @Size(max = 100, message = "分类名称长度不能超过 100")
    private String categoryName;
}
