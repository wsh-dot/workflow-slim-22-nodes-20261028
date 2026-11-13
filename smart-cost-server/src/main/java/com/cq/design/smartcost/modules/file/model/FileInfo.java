package com.cq.design.smartcost.modules.file.model;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_file，业务文件登记记录。 */
@Data
@TableName("sc_file")
public class FileInfo {
    @TableId(type = IdType.INPUT)
    private String id;
    /** 归属对象类型字典编码：PROJECT 或 BATCH 等。 */
    @TableField("master_type")
    private String masterType;
    /** 归属对象 UUID，必填；须先创建业务主记录再上传文件。 */
    @TableField("master_id")
    private String masterId;
    @TableField("batch_no")
    private Integer batchNo;
    /** 文件类型字典编码，可为空。 */
    private String type;
    /** 文件状态字典编码，可为空。 */
    private String status;
    @TableField("original_name")
    private String originalName;
    /** 程序生成的实际存储文件名。 */
    @TableField("stored_name")
    private String storedName;
    /** 相对于文件根目录的目录路径，与 stored_name 拼接即存储键。 */
    @TableField("file_path")
    private String filePath;
    private String extension;
    @TableField("mime_type")
    private String mimeType;
    /** 文件大小，单位字节。 */
    private Long size;
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;
}
