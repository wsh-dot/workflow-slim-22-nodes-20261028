package com.cq.design.smartcost.modules.project.dto;

import lombok.Data;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 项目新增/修改请求输入。 */
@Data
public class ProjectInput {
    /** 项目编码，全库唯一。 */
    @NotBlank(message = "项目编码不能为空")
    @Size(max = 40, message = "项目编码长度不能超过 40")
    private String code;

    /** 项目名称。 */
    @NotBlank(message = "项目名称不能为空")
    @Size(max = 100, message = "项目名称长度不能超过 100")
    private String name;

    /** 项目关键说明。 */
    @Size(max = 1000, message = "项目关键说明长度不能超过 1000")
    private String keyInfo;

    /** 所属专业字典编码，可为空。 */
    @Size(max = 32, message = "所属专业编码长度不能超过 32")
    private String specialtyCode;

    /** 项目状态字典编码。 */
    @Size(max = 32, message = "项目状态编码长度不能超过 32")
    private String status;
}
