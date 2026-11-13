package com.cq.design.smartcost.modules.raw.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.raw.dto.FileItemNodeView;
import com.cq.design.smartcost.modules.raw.dto.QuantityCbsNodeView;
import com.cq.design.smartcost.modules.raw.dto.QuantitySummary;
import com.cq.design.smartcost.modules.raw.service.QuantityStructureService;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 工程量编制接口：提供 CBS 树、工程量列表、未挂接列表、统计查询及挂接/取消挂接。
 * 全部接口按批次隔离（batchId 必传），不同批次的挂接结果互不影响。
 */
@RestController
@RequestMapping("/raw/quantity")
public class QuantityStructureController {

    @Resource(name = "quantityStructureService")
    private QuantityStructureService service;

    /** 汇总统计（按批次）：结构项总数与未挂接数量。 */
    @GetMapping("/summary")
    public ApiResponse<QuantitySummary> summary(@RequestParam String projectId, @RequestParam String batchId) {
        return ApiResponse.success(service.summary(projectId, batchId));
    }

    /** 左侧 CBS 树（按批次）：项目 CBS 结构 + 每节点挂接工程量数量。 */
    @GetMapping("/cbs-tree")
    public ApiResponse<List<QuantityCbsNodeView>> cbsTree(@RequestParam String projectId,
            @RequestParam String batchId) {
        return ApiResponse.success(service.cbsTree(projectId, batchId));
    }

    /** 指定批次下挂到某 CBS 最底层节点的工程量列表（线性结构）。 */
    @GetMapping("/items")
    public ApiResponse<List<FileItemNodeView>> items(@RequestParam String cbsId, @RequestParam String batchId) {
        return ApiResponse.success(service.itemsByCbs(cbsId, batchId));
    }

    /** 未挂接的工程量列表（线性结构，只含设备/主材；按批次隔离）。 */
    @GetMapping("/unattached")
    public ApiResponse<List<FileItemNodeView>> unattached(@RequestParam String projectId,
            @RequestParam String batchId) {
        return ApiResponse.success(service.unattachedList(projectId, batchId));
    }

    /** 手工挂接：把该批次的工程量项挂到指定 CBS 最底层节点，返回同批次最新汇总统计。 */
    @PostMapping("/attach")
    public ApiResponse<QuantitySummary> attach(@RequestParam String itemId, @RequestParam String cbsId,
            @RequestParam String batchId) {
        return ApiResponse.success(service.attach(itemId, cbsId, batchId));
    }

    /** 批量挂接：把某张料表下全部未挂接的设备/主材挂到指定 CBS 节点，返回同批次最新汇总统计。 */
    @PostMapping("/attach-batch")
    public ApiResponse<QuantitySummary> attachBatch(@RequestParam String fileId, @RequestParam String cbsId,
            @RequestParam String batchId) {
        return ApiResponse.success(service.attachByFile(fileId, cbsId, batchId));
    }

    /** 取消挂接：把已挂接的工程量项恢复为未挂接，返回同批次最新汇总统计。 */
    @PostMapping("/detach")
    public ApiResponse<QuantitySummary> detach(@RequestParam String itemId, @RequestParam String batchId) {
        return ApiResponse.success(service.detach(itemId, batchId));
    }
}
