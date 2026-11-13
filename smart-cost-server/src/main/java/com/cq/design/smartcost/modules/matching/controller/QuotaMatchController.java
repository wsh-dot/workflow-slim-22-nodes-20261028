package com.cq.design.smartcost.modules.matching.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.matching.dto.QuotaCellUpdateInput;
import com.cq.design.smartcost.modules.matching.dto.QuotaManualMatchInput;
import com.cq.design.smartcost.modules.matching.dto.QuotaMatchView;
import com.cq.design.smartcost.modules.matching.service.QuotaMatchService;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 定额/指标匹配接口：按批次 + CBS 最底层节点查询匹配结果树，
 * 右侧表格的「单位/工程量计算式/工程量」可编辑并落库。
 */
@RestController
@RequestMapping("/matching/quota")
public class QuotaMatchController {

    @Resource(name = "quotaMatchService")
    private QuotaMatchService service;

    /** 指定批次下挂到某 CBS 最底层节点的定额匹配树（根=定额，子=人材机消耗）。 */
    @GetMapping("/items")
    public ApiResponse<List<QuotaMatchView>> items(@RequestParam String cbsId, @RequestParam String batchId) {
        return ApiResponse.success(service.items(cbsId, batchId));
    }

    /** 更新定额根节点可编辑字段：单位、工程量计算式、工程量。 */
    @PostMapping("/update-match")
    public ApiResponse<Void> updateMatch(@RequestBody QuotaCellUpdateInput input) {
        service.updateMatch(input);
        return ApiResponse.success(null);
    }

    /** 更新人材机消耗子节点可编辑字段：单位、工程量计算式、工程量。 */
    @PostMapping("/update-consume")
    public ApiResponse<Void> updateConsume(@RequestBody QuotaCellUpdateInput input) {
        service.updateConsume(input);
        return ApiResponse.success(null);
    }

    /** 人工选择定额/指标：把匹配记录手动指定为定额知识库中的某个子目。 */
    @PostMapping("/manual-match")
    public ApiResponse<Void> manualMatch(@RequestBody QuotaManualMatchInput input) {
        service.manualMatch(input);
        return ApiResponse.success(null);
    }

    /** 升级为独立计价项：置空定额关联（状态置已处理 1403）并清理消耗明细，仅设备/主材可升级。 */
    @PostMapping("/upgrade/{matchId}")
    public ApiResponse<Void> upgrade(@PathVariable String matchId) {
        service.upgrade(matchId);
        return ApiResponse.success(null);
    }
}
