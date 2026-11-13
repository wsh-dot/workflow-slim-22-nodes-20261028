package com.cq.design.smartcost.modules.raw.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.raw.dto.MaterialFileView;
import com.cq.design.smartcost.modules.raw.service.RawMaterialFileService;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 料表文件接口：批量上传料表到项目当前批次并解析，查询当前批次的料表文件。
 *
 * <p>文件列表与下载复用通用文件接口（/file/list、/file/{id}/download、/file/{id}/preview）。</p>
 */
@RestController
@RequestMapping("/raw/material-files")
public class RawMaterialFileController {
    @Resource(name = "rawMaterialFileService")
    private RawMaterialFileService service;

    /** 批量上传料表文件：PDF 上传后立即解析，其他格式登记为待解析。 */
    @PostMapping("/upload")
    public ApiResponse<List<FileInfo>> upload(@RequestParam String projectId,
            @RequestParam("files") List<MultipartFile> files) {
        return ApiResponse.success(service.uploadAndParse(projectId, files));
    }

    /** 查询项目当前批次的料表文件列表（含分析状态：sc_file_item 是否存在关联数据），按上传时间倒序。 */
    @GetMapping
    public ApiResponse<List<MaterialFileView>> list(@RequestParam String projectId) {
        return ApiResponse.success(service.listByProject(projectId));
    }

    /** 重新解析指定料表文件：清除旧解析数据并按当前解析器重新解析；失败时旧数据保持不变。 */
    @PostMapping("/{fileId}/reparse")
    public ApiResponse<FileInfo> reparse(@PathVariable String fileId) {
        return ApiResponse.success(service.reparse(fileId));
    }

    /** 删除料表文件及其解析数据（表头、原始行一并清除）。 */
    @DeleteMapping("/{fileId}")
    public ApiResponse<Void> delete(@PathVariable String fileId) {
        service.deleteMaterialFile(fileId);
        return ApiResponse.success(null);
    }
}
