package com.cq.design.smartcost.modules.project.model;


import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_project_cbs。 */
@TableName("sc_project_cbs")
@Data
public class ProjectCbs {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("project_id")
    private String projectId;
    @TableField("parent_id")
    private String parentId;
    private String code;
    private String name;
    @TableField("source_detail_name")
    private String sourceDetailName;
    @TableField("category_code")
    private String categoryCode;
    @TableField("category_name")
    private String categoryName;
    @TableField("sort_no")
    private Integer sortNo;
    @TableField("inner_code")
    private String innerCode;
    @TableField("source_cbs_id")
    private String sourceCbsId;
    @TableField("source_cbs_detail_id")
    private String sourceCbsDetailId;
    @TableField("source_version_no")
    private Integer sourceVersionNo;
    private String remark;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
