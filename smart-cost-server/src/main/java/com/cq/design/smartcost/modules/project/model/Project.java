package com.cq.design.smartcost.modules.project.model;


import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/** 对应数据库表 sc_project。 */
@TableName("sc_project")
@Data
public class Project {
    private String id;
    private String code;
    private String name;
    @TableField("key_info")
    private String keyInfo;
    @TableField("specialty_code")
    private String specialtyCode;
    private String status;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
