package com.cq.design.smartcost.modules.project.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 项目 CBS 节点移动请求：调整同级顺序或父子关系。
 *
 * <p>移动方向：</p>
 * <ul>
 *   <li>UP —— 在同级中上移一位</li>
 *   <li>DOWN —— 在同级中下移一位</li>
 *   <li>PROMOTE —— 升级，变为父节点的同级节点（挂到父节点的父节点下）</li>
 *   <li>DEMOTE —— 降级，变为前一个兄弟节点的子节点</li>
 * </ul>
 */
@Data
public class ProjectCbsMoveInput {
    /** 所属项目 UUID。 */
    @NotBlank(message = "项目ID不能为空")
    private String projectId;

    /** 移动方向，取值 UP / DOWN / PROMOTE / DEMOTE。 */
    @NotBlank(message = "移动方向不能为空")
    private String direction;
}
