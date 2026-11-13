package com.cq.design.smartcost.modules.project.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.common.web.PageResult;
import com.cq.design.smartcost.modules.project.dto.*;
import com.cq.design.smartcost.modules.project.service.ProjectService;
import jakarta.annotation.Resource;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

/** 项目接口：项目主表 sc_project 的增删改查入口。 */
@RestController
@RequestMapping("/smartCost/project")
public class ProjectController {
    @Resource(name = "projectService")
    private ProjectService service;

    /** 分页查询项目列表，支持按编码或名称模糊搜索，含审计字段名称。 */
    @GetMapping
    public ApiResponse<PageResult<ProjectView>> list(ProjectQueryInput input) {
        return ApiResponse.success(service.list(input));
    }

    /** 查询单个项目详情，含审计字段名称。 */
    @GetMapping("/{id}")
    public ApiResponse<ProjectView> get(@PathVariable String id) {
        return ApiResponse.success(service.get(id));
    }

    /** 查询项目最新批次（批次号最大）：返回批次状态与当前组价节点，无批次时返回 null。 */
    @GetMapping("/{id}/batch")
    public ApiResponse<BatchView> getCurrentBatch(@PathVariable String id) {
        return ApiResponse.success(service.getCurrentBatch(id));
    }

    /** 推进批次当前组价节点（流程「下一步」）。 */
    @PutMapping("/{id}/batch/stage")
    public ApiResponse<BatchView> advanceStage(@PathVariable String id, @RequestParam String stage) {
        return ApiResponse.success(service.advanceStage(id, stage));
    }

    /** 新增项目，项目编码唯一。 */
    @PostMapping
    public ApiResponse<ProjectView> create(@Valid @RequestBody ProjectInput input) {
        return ApiResponse.success(service.create(input));
    }

    /**
     * 初始化项目基础数据：创建默认批次与 CBS 根节点。
     *
     * <p>幂等操作，已存在时直接复用；供设计说明文件上传成功后调用。</p>
     */
    @PostMapping("/{id}/initialize")
    public ApiResponse<ProjectInitResult> initialize(@PathVariable String id) {
        return ApiResponse.success(service.initialize(id));
    }

    /** 修改项目资料。 */
    @PutMapping("/{id}")
    public ApiResponse<ProjectView> update(@PathVariable String id, @Valid @RequestBody ProjectInput input) {
        return ApiResponse.success(service.update(id, input));
    }

    /** 删除项目；存在批次、CBS 结构或文件时禁止删除。 */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        service.delete(id);
        return ApiResponse.success(null);
    }
}
