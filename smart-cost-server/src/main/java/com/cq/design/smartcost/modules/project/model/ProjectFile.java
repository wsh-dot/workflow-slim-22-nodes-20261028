package com.cq.design.smartcost.modules.project.model;


import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/** 对应数据库表 sc_file。 */
@TableName("sc_file")
@Data
public class ProjectFile {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("master_type")
    private String masterType;
    @TableField("master_id")
    private String masterId;
    @TableField("batch_no")
    private Integer batchNo;
    private String type;
    @TableField("status")
    private String status;
    @TableField("original_name")
    private String originalName;
    @TableField("stored_name")
    private String storedName;
    @TableField("file_path")
    private String filePath;
    private String extension;
    @TableField("mime_type")
    private String mimeType;
    private Long size;
    @TableField("create_user_id")
    private String createUserId;
    @TableField("create_org_id")
    private String createOrgId;
    @TableField("create_date")
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
