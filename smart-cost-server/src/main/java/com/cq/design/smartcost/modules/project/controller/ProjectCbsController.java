package com.cq.design.smartcost.modules.project.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.project.dto.*;
import com.cq.design.smartcost.modules.project.service.ProjectCbsDeLibraryService;
import com.cq.design.smartcost.modules.project.service.ProjectCbsService;
import com.cq.design.smartcost.modules.quota.dto.QuotaLibraryView;
import jakarta.annotation.Resource;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/** 项目 CBS 接口：项目结构树查询、标准结构引入与节点维护。 */
@RestController
@RequestMapping("/smartCost/project/cbs")
public class ProjectCbsController {
    @Resource(name = "projectCbsService")
    private ProjectCbsService service;
    @Resource(name = "projectCbsDeLibraryService")
    private ProjectCbsDeLibraryService deLibraryService;

    /** 查询项目 CBS 树，按 parent_id 还原层级。 */
    @GetMapping("/tree")
    public ApiResponse<List<ProjectCbsNodeView>> tree(@RequestParam String projectId) {
        return ApiResponse.success(service.tree(projectId));
    }

    /**
     * 把平台标准结构引入项目 CBS。
     *
     * <p>服务端重新查询平台模板树，按级联规则计算最终引入的节点集合并重新生成父子关系。</p>
     */
    @PostMapping("/import")
    public ApiResponse<ProjectCbsImportResult> importStandard(@Valid @RequestBody ProjectCbsImportInput input) {
        return ApiResponse.success(service.importFromStandard(input));
    }

    /** 在选中节点下新增一个自建节点，返回新节点 UUID。 */
    @PostMapping("/node")
    public ApiResponse<String> createNode(@RequestParam String projectId,
            @Valid @RequestBody ProjectCbsNodeInput input) {
        return ApiResponse.success(service.createNode(projectId, input));
    }

    /** 修改项目 CBS 节点名称与分类（改名只改显示名称，不改标准节点原始名称快照）。 */
    @PutMapping("/node/{nodeId}")
    public ApiResponse<Void> updateNode(@RequestParam String projectId, @PathVariable String nodeId,
            @Valid @RequestBody ProjectCbsNodeInput input) {
        service.updateNode(projectId, nodeId, input);
        return ApiResponse.success(null);
    }

    /** 删除项目 CBS 节点及其全部下级。 */
    @DeleteMapping("/node/{nodeId}")
    public ApiResponse<Void> deleteNode(@RequestParam String projectId, @PathVariable String nodeId) {
        service.deleteNode(projectId, nodeId);
        return ApiResponse.success(null);
    }

    /** 复制项目 CBS 节点及其全部下级，副本插入到同级位置，返回副本根节点 UUID。 */
    @PostMapping("/node/{nodeId}/copy")
    public ApiResponse<String> copyNode(@RequestParam String projectId, @PathVariable String nodeId) {
        return ApiResponse.success(service.copyNode(projectId, nodeId));
    }

    /** 移动项目 CBS 节点：上移/下移调整同级顺序，升级/降级调整父子关系。 */
    @PostMapping("/node/{nodeId}/move")
    public ApiResponse<ProjectCbsOperationResult> moveNode(@PathVariable String nodeId,
            @Valid @RequestBody ProjectCbsMoveInput input) {
        return ApiResponse.success(service.moveNode(input.getProjectId(), nodeId, input));
    }

    /** 查询项目下所有 CBS 节点已挂载的定额库。 */
    @GetMapping("/de-libraries")
    public ApiResponse<List<ProjectCbsDeLibraryView>> deLibraries(@RequestParam String projectId) {
        return ApiResponse.success(deLibraryService.listByProject(projectId));
    }

    /** 为项目 CBS 节点挂载定额库，一个节点可挂载多个。 */
    @PostMapping("/de-libraries")
    public ApiResponse<Integer> mountDeLibraries(@Valid @RequestBody ProjectCbsDeLibraryInput input) {
        return ApiResponse.success(deLibraryService.mount(input.getProjectId(), input));
    }

    /** 解除项目 CBS 节点与定额库的挂载。 */
    @DeleteMapping("/de-libraries/{relationId}")
    public ApiResponse<Integer> unmountDeLibrary(@RequestParam String projectId, @PathVariable String relationId) {
        return ApiResponse.success(deLibraryService.unmount(projectId, relationId));
    }

    /** 查询可供挂载的定额库列表。 */
    @GetMapping("/de-library-options")
    public ApiResponse<List<QuotaLibraryView>> deLibraryOptions() {
        return ApiResponse.success(deLibraryService.libraryOptions());
    }
}
