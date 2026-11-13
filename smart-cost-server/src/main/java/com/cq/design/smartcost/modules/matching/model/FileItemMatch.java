package com.cq.design.smartcost.modules.matching.model;


import lombok.Data;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.TableField;
import java.math.BigDecimal;

/** 对应数据库表 sc_file_item_match。 */
@TableName("sc_file_item_match")
@Data
public class FileItemMatch {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("file_item_id")
    private String fileItemId;
    @TableField("de_library_id")
    private String deLibraryId;
    @TableField("de_item_id")
    private String deItemId;
    /** 是否主定额：0=非主定额，1=主定额。 */
    @TableField("is_main")
    private Integer isMain;
    private String code;
    private String name;
    private String unit;
    private String formula;
    private BigDecimal quantity;
    @TableField("base_price")
    private BigDecimal basePrice;
    @TableField("cl_fee")
    private BigDecimal clFee;
    @TableField("rg_fee")
    private BigDecimal rgFee;
    @TableField("jx_fee")
    private BigDecimal jxFee;
    @TableField("zc_fee")
    private BigDecimal zcFee;
    @TableField("sb_fee")
    private BigDecimal sbFee;
    @TableField("match_status")
    private String matchStatus;
    @TableField("match_method")
    private String matchMethod;
    @TableField("match_score")
    private BigDecimal matchScore;
    @TableField("material_handling")
    private String materialHandling;
    @TableField("match_remark")
    private String matchRemark;
    @TableField("create_user_id")
    private String createUserId;
    @TableField("create_org_id")
    private String createOrgId;
    @TableField("create_date")
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
