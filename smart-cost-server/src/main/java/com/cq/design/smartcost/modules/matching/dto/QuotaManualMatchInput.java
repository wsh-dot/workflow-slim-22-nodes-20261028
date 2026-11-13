package com.cq.design.smartcost.modules.matching.dto;

import lombok.Data;

/** 人工选择定额/指标入参：将匹配记录手动指定为定额知识库中的某个子目，可同时指定关联定额。 */
@Data
public class QuotaManualMatchInput {
    /** 定额匹配记录 UUID（sc_file_item_match.id）。 */
    private String matchId;
    /** 选中的定额/指标子目 UUID（sc_de_item.id）。 */
    private String deItemId;
    /** 关联定额子目 UUID（sc_de_item.id）；为空表示只选主定额。 */
    private String relatedDeItemId;
    /** 原始定额工作量（A-06 规则标准工作量）；为空按 1 处理。 */
    private String originQuantity;
    /** 关联定额工作量（A-06 规则标准工作量）；换算系数 = 关联工作量 / 原始工作量。 */
    private String relatedQuantity;
}
