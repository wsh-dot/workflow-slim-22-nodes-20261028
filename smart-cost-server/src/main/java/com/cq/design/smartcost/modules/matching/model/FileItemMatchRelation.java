package com.cq.design.smartcost.modules.matching.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/** 对应主定额与关联定额匹配结果关系表。 */
@TableName("sc_file_item_match_relation")
@Data
public class FileItemMatchRelation {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("source_match_id")
    private String sourceMatchId;
    @TableField("associated_match_id")
    private String associatedMatchId;
}
