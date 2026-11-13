package com.cq.design.smartcost.modules.raw.model;


import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_file_header。 */
@TableName("sc_file_header")
@Data
public class FileHeader {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("file_id")
    private String fileId;
    @TableField("table_type")
    private String tableType;
    @TableField("specialty_name")
    private String specialtyName;
    @TableField("project_section")
    private String projectSection;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
