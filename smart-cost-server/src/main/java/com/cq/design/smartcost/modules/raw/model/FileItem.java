package com.cq.design.smartcost.modules.raw.model;


import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;

/** 对应数据库表 sc_file_item。 */
@TableName("sc_file_item")
@Data
public class FileItem {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("file_id")
    private String fileId;
    @TableField("project_cbs_id")
    private String projectCbsId;
    @TableField("parent_id")
    private String parentId;
    @TableField("sort_no")
    private Integer sortNo;
    private String type;
    private String code;
    private String name;
    private String specification;
    private String unit;
    private BigDecimal quantity;
    private String remark;
    @TableField("cbs_match_status")
    private String cbsMatchStatus;
    @TableField("cbs_match_method")
    private String cbsMatchMethod;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
