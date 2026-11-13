package com.cq.design.smartcost.modules.matching.model;


import lombok.Data;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.TableField;
import java.math.BigDecimal;

/** 对应数据库表 sc_file_item_match_consume。 */
@TableName("sc_file_item_match_consume")
@Data
public class FileItemMatchConsume {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("match_id")
    private String matchId;
    @TableField("source_de_consume_id")
    private String sourceDeConsumeId;
    @TableField("source_file_item_id")
    private String sourceFileItemId;
    private String code;
    private String name;
    private String type;
    private String unit;
    private String formula;
    private BigDecimal quantity;
    @TableField("original_price")
    private BigDecimal originalPrice;
    private BigDecimal price;
    @TableField("price_match_status")
    private String priceMatchStatus;
    @TableField("price_match_method")
    private String priceMatchMethod;
    @TableField("price_match_score")
    private BigDecimal priceMatchScore;
    @TableField("price_match_remark")
    private String priceMatchRemark;
    @TableField("sort_no")
    private Integer sortNo;
    private String remark;
    @TableField("create_user_id")
    private String createUserId;
    @TableField("create_org_id")
    private String createOrgId;
    @TableField("create_date")
    private String createDate;

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    

    
}
