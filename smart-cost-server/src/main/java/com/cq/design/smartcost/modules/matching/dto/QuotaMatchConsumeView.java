package com.cq.design.smartcost.modules.matching.dto;

import lombok.Data;

/** 定额/指标匹配结果子节点视图：对应 sc_file_item_match_consume（人材机消耗）。 */
@Data
public class QuotaMatchConsumeView {
    /** 消耗记录 UUID。 */
    private String id;
    /** 所属定额匹配记录 UUID（sc_file_item_match.id）。 */
    private String matchId;
    /** 消耗项编号。 */
    private String code;
    /** 消耗项名称。 */
    private String name;
    /** 人材机类型（字典16）：1601 人工、1602 材料、1603 机械、1604 主材、1605 设备。 */
    private String type;
    /** 计量单位（可编辑）。 */
    private String unit;
    /** 工程量计算式（可编辑）。 */
    private String formula;
    /** 工程量（可编辑）。 */
    private String quantity;
    /** 单价（price）。 */
    private String price;
    /** 排序号。 */
    private Integer sortNo;
}
