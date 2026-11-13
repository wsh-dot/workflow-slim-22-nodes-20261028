package com.cq.design.smartcost.modules.project.model;


import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_project_cbs_de_library。 */
@TableName("sc_project_cbs_de_library")
@Data
public class ProjectCbsDeLibrary {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("project_id")
    private String projectId;
    @TableField("project_cbs_id")
    private String projectCbsId;
    @TableField("de_library_id")
    private String deLibraryId;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
