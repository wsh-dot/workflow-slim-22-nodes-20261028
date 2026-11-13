package com.cq.design.smartcost.modules.raw.dto;

import lombok.Data;

/** 工程量结构汇总统计：用于页签角标与下一步校验。 */
@Data
public class QuantitySummary {
    /** 工程量结构项总数。 */
    private long totalItems;
    /** 未挂接（未匹配到 CBS 单位工程）的结构项数量。 */
    private long unattachedItems;
}
