package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;

/** 项目列表分页查询输入。 */
@Data
public class ProjectQueryInput {
    /** 页码，从 1 开始。 */
    private Integer page = 1;

    /** 每页条数，服务端限制最大 100。 */
    private Integer size = 20;

    /** 关键字，模糊匹配项目编码或名称。 */
    private String keyword;
}
