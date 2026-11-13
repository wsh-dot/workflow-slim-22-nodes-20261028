package com.cq.design.smartcost.modules.project.dto;

import com.cq.design.smartcost.modules.project.model.Project;
import lombok.Data;
import lombok.EqualsAndHashCode;

/** 项目列表/详情返回视图：在实体基础上补充审计 ID 对应的名称，避免前端再查字典。 */
@Data
@EqualsAndHashCode(callSuper = true)
public class ProjectView extends Project {
    /** 创建人姓名，对应 create_user_id。 */
    private String createUserName;

    /** 创建机构名称，对应 create_org_id。 */
    private String createOrgName;
}
