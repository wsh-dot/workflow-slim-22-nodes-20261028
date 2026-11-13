package com.cq.design.smartcost.modules.file.controller;

import com.cq.design.smartcost.common.web.ApiResponse;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.file.service.FileService;
import jakarta.annotation.Resource;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 通用文件接口：任意业务对象（masterType + masterId）的文件上传、列表、下载与删除。
 *
 * <p>作为与具体业务解耦的通用能力，路径不挂业务前缀；上传属于 multipart 请求，
 * 经统一的会话认证与 CSRF 校验。</p>
 */
@RestController
@RequestMapping("/file")
public class FileController {
    @Resource(name = "fileService")
    private FileService service;

    /**
     * 上传文件并登记元数据。
     *
     * @param file 上传的文件内容
     * @param masterType 归属对象类型字典编码，如 PROJECT、BATCH
     * @param masterId 归属对象 UUID，必填；须先创建业务主记录再上传
     * @param type 文件类型字典编码，可为空
     */
    @PostMapping("/upload")
    public ApiResponse<FileInfo> upload(@RequestParam("file") MultipartFile file,
            @RequestParam String masterType,
            @RequestParam String masterId,
            @RequestParam(required = false) String type) {
        return ApiResponse.success(service.upload(file, masterType, masterId, type));
    }

    /** 查询归属对象下的全部文件，按上传时间倒序。 */
    @GetMapping("/list")
    public ApiResponse<List<FileInfo>> list(@RequestParam String masterType,
            @RequestParam String masterId) {
        return ApiResponse.success(service.list(masterType, masterId));
    }

    /** 下载文件，按原始文件名返回。 */
    @GetMapping("/{id}/download")
    public ResponseEntity<InputStreamResource> download(@PathVariable String id) {
        FileInfo info = service.get(id);
        try {
            InputStream content = service.open(info);
            String encodedName = URLEncoder.encode(
                    info.getOriginalName() == null ? "file" : info.getOriginalName(),
                    StandardCharsets.UTF_8).replace("+", "%20");
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "attachment; filename*=UTF-8''" + encodedName)
                    .contentType(MediaType.parseMediaType(
                            info.getMimeType() == null ? "application/octet-stream" : info.getMimeType()))
                    .body(new InputStreamResource(content));
        } catch (IOException exception) {
            throw new com.cq.design.smartcost.common.web.BusinessException("文件读取失败，可能已被清理");
        }
    }

    /** 在线预览文件：以内联方式返回，浏览器可直接展示 PDF 等可预览格式。 */
    @GetMapping("/{id}/preview")
    public ResponseEntity<InputStreamResource> preview(@PathVariable String id) {
        FileInfo info = service.get(id);
        try {
            InputStream content = service.open(info);
            String encodedName = URLEncoder.encode(
                    info.getOriginalName() == null ? "file" : info.getOriginalName(),
                    StandardCharsets.UTF_8).replace("+", "%20");
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "inline; filename*=UTF-8''" + encodedName)
                    .contentType(MediaType.parseMediaType(
                            info.getMimeType() == null ? "application/octet-stream" : info.getMimeType()))
                    .body(new InputStreamResource(content));
        } catch (IOException exception) {
            throw new com.cq.design.smartcost.common.web.BusinessException("文件读取失败，可能已被清理");
        }
    }

    /** 删除文件登记记录及物理文件。 */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        service.delete(id);
        return ApiResponse.success(null);
    }
}
