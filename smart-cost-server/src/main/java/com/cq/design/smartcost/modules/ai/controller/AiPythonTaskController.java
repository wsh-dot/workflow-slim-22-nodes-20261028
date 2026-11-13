package com.cq.design.smartcost.modules.ai.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.ai.dto.AiPythonTaskView;
import com.cq.design.smartcost.modules.ai.service.AiPythonTaskService;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

/**
 * AI Python 任务接口：下一步/重新构建时创建任务（写 sc_ai_python_task），
 * 前端轮询任务状态直到 Python 端把 status 置为 1。
 */
@RestController
@RequestMapping("/ai/task")
public class AiPythonTaskController {
    @Resource(name = "aiPythonTaskService")
    private AiPythonTaskService aiPythonTaskService;

    /**
     * 创建 AI 处理任务：taskType 为下一组价节点编码（0901/0902/...）。
     *
     * @param hasError 当前任务类型的最新任务是否带错误信息（即失败重试）：
     *                 true 时不改动批次 sc_file 状态，false（首次执行）才全量置待处理
     */
    @PostMapping("/create")
    public ApiResponse<AiPythonTaskView> create(@RequestParam String projectId,
            @RequestParam String taskType,
            @RequestParam(defaultValue = "false") Boolean hasError) {
        return ApiResponse.success(aiPythonTaskService.createTask(projectId, taskType, hasError));
    }

    /**
     * 查询项目最新任务状态（可按 taskType 过滤），供前端轮询。
     * 任务已完成（status = 1）时顺带把批次节点推进到任务对应节点（幂等）。
     */
    @GetMapping("/latest")
    public ApiResponse<AiPythonTaskView> latest(@RequestParam String projectId,
            @RequestParam(required = false) String taskType) {
        return ApiResponse.success(aiPythonTaskService.latestTask(projectId, taskType));
    }
}
