package com.cq.design.smartcost.modules.file.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cq.design.smartcost.common.file.FileStorage;
import com.cq.design.smartcost.common.file.StoredFile;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.file.dao.FileInfoDao;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Locale;

/** 通用业务文件服务：任意业务对象（masterType + masterId）的文件上传、查询、下载与删除。 */
@Service
public class FileService extends BusinessService {
    private static final org.slf4j.Logger log =
            org.slf4j.LoggerFactory.getLogger(FileService.class);

    @Resource(name = "fileInfoDao")
    private FileInfoDao dao;
    @Resource
    private FileStorage fileStorage;

    /**
     * 保存上传文件并登记 sc_file 记录。
     *
     * <p>文件必须归属已存在的业务对象：masterType + masterId 均为必填，
     * 由调用方在业务主记录创建成功后再发起上传，避免产生无主死数据。</p>
     */
    public FileInfo upload(MultipartFile file, String masterType, String masterId, String type) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException("请选择要上传的文件");
        }
        if (!StringUtils.hasText(masterType)) {
            throw new BusinessException("文件归属对象类型不能为空");
        }
        if (!StringUtils.hasText(masterId)) {
            throw new BusinessException("文件归属对象标识不能为空，请先创建业务数据再上传文件");
        }
        StoredFile stored;
        try (InputStream content = file.getInputStream()) {
            stored = fileStorage.store(file.getOriginalFilename(), content);
        } catch (IOException exception) {
            log.error("保存上传文件失败：{}", file.getOriginalFilename(), exception);
            throw new BusinessException("文件上传失败，请稍后重试");
        }
        FileInfo info = new FileInfo();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        info.setMasterType(masterType.trim().toUpperCase(Locale.ROOT));
        info.setMasterId(StringUtils.hasText(masterId) ? masterId.trim() : null);
        info.setType(StringUtils.hasText(type) ? type.trim() : null);
        info.setOriginalName(normalizeOriginalName(file.getOriginalFilename()));
        splitStorageKey(stored.getStorageKey(), info);
        info.setExtension(extractExtension(stored.getOriginalFilename()));
        info.setMimeType(file.getContentType());
        info.setSize(stored.getSize());
        dao.insert(info);
        return info;
    }

    /** 查询归属对象下的全部文件，按上传时间倒序。 */
    public List<FileInfo> list(String masterType, String masterId) {
        if (!StringUtils.hasText(masterType) || !StringUtils.hasText(masterId)) {
            throw new BusinessException("文件归属对象不能为空");
        }
        return dao.selectList(new QueryWrapper<FileInfo>()
                .eq("master_type", masterType.trim().toUpperCase(Locale.ROOT))
                .eq("master_id", masterId.trim())
                .orderByDesc("create_date"));
    }

    /** 按主键查询文件登记记录。 */
    public FileInfo get(String id) {
        FileInfo current = dao.selectById(id);
        if (current == null) {
            throw new BusinessException("文件不存在");
        }
        return current;
    }

    /** 打开文件内容流，由控制器负责写出并关闭。 */
    public InputStream open(FileInfo info) throws IOException {
        return fileStorage.open(storageKey(info));
    }

    /**
     * 删除文件登记记录；物理文件在事务提交后删除，登记失败不影响记录删除。
     */
    public void delete(String id) {
        FileInfo current = get(id);
        dao.deleteById(current.getId());
        String key = storageKey(current);
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    fileStorage.delete(key);
                } catch (IOException exception) {
                    log.warn("删除物理文件失败，storageKey={}", key, exception);
                }
            }
        });
    }

    /** 删除物理文件但不登记数据库；供业务回滚后清理已落盘的孤儿文件。 */
    public void deletePhysicalFile(FileInfo info) {
        try {
            fileStorage.delete(storageKey(info));
        } catch (IOException exception) {
            log.warn("清理物理文件失败，storageKey={}", storageKey(info), exception);
        }
    }

    /** 由目录路径与存储文件名还原存储键。 */
    private String storageKey(FileInfo info) {
        return StringUtils.hasText(info.getFilePath())
                ? info.getFilePath() + "/" + info.getStoredName()
                : info.getStoredName();
    }

    /** 将存储键拆分为目录路径与文件名，避免把整段键写进 stored_name。 */
    private void splitStorageKey(String storageKey, FileInfo info) {
        int separatorIndex = storageKey.lastIndexOf('/');
        if (separatorIndex >= 0) {
            info.setFilePath(storageKey.substring(0, separatorIndex));
            info.setStoredName(storageKey.substring(separatorIndex + 1));
        } else {
            info.setFilePath(null);
            info.setStoredName(storageKey);
        }
    }

    /** 提取小写扩展名（不含点），无扩展名时返回 null。 */
    private String extractExtension(String originalName) {
        String name = StringUtils.hasText(originalName) ? originalName : "";
        int dotIndex = name.lastIndexOf('.');
        if (dotIndex < 0 || dotIndex == name.length() - 1) {
            return null;
        }
        return name.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
    }

    /** 去掉浏览器可能携带的路径部分，仅保留文件名。 */
    private String normalizeOriginalName(String originalName) {
        String name = StringUtils.hasText(originalName) ? originalName : "未命名文件";
        String normalized = name.replace('\\', '/');
        int slashIndex = normalized.lastIndexOf('/');
        return slashIndex >= 0 ? normalized.substring(slashIndex + 1) : normalized;
    }
}
