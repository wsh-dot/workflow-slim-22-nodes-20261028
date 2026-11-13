package com.cq.design.smartcost.modules.project.model;


import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_batch。 */
@TableName("sc_batch")
@Data
public class Batch {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("project_id")
    private String projectId;
    @TableField("batch_no")
    private Integer batchNo;
    private String status;
    @TableField("current_stage")
    private String currentStage;
    @TableField("pricing_completed_at")
    private String pricingCompletedAt;
    @TableField("calculation_completed_at")
    private String calculationCompletedAt;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
