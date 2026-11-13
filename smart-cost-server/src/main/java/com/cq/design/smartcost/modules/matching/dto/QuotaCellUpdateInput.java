package com.cq.design.smartcost.modules.matching.dto;

import lombok.Data;

import java.math.BigDecimal;

/** 定额/指标匹配单元格编辑入参：单位、工程量计算式、工程量允许修改。 */
@Data
public class QuotaCellUpdateInput {
    /** 记录 UUID（sc_file_item_match.id 或 sc_file_item_match_consume.id）。 */
    private String id;
    /** 计量单位；传 null 表示清空。 */
    private String unit;
    /** 工程量计算式；传 null 表示清空。 */
    private String formula;
    /** 工程量；传 null 表示清空。 */
    private BigDecimal quantity;
}
