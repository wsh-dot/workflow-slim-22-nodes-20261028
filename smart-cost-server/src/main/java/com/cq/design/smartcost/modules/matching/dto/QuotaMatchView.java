package com.cq.design.smartcost.modules.matching.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/** 定额/指标匹配结果根节点视图：对应 sc_file_item_match，子节点为人材机消耗。 */
@Data
public class QuotaMatchView {
    /** 定额匹配记录 UUID。 */
    private String id;
    /** 关联的工程量结构项 UUID（sc_file_item.id）。 */
    private String fileItemId;
    /** 关联工程量结构项的类型（sc_file_item.type，字典13）：1302 主材、1303 设备、1301 分部。 */
    private String itemType;
    /** 是否主定额：0=非主定额，1=主定额。 */
    private Integer isMain;
    /** 定额编号。 */
    private String code;
    /** 定额名称。 */
    private String name;
    /** 计量单位（可编辑）。 */
    private String unit;
    /** 工程量计算式（可编辑）。 */
    private String formula;
    /** 工程量（可编辑）。 */
    private String quantity;
    /** 单价（base_price）。 */
    private String price;
    /** 匹配状态（字典14）：1401 已命中、1402 未命中、1403 已处理。 */
    private String matchStatus;
    /** 匹配方式（字典15）：1501 自动、1502 人工。 */
    private String matchMethod;
    /** 子节点：人材机消耗（sc_file_item_match_consume）。 */
    private List<QuotaMatchConsumeView> children = new ArrayList<>();
}
