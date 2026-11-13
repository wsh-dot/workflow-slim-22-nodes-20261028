package com.cq.design.smartcost.modules.raw.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cq.design.smartcost.common.constants.Constants;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.file.dao.FileInfoDao;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.file.service.FileService;
import com.cq.design.smartcost.modules.project.dao.BatchDao;
import com.cq.design.smartcost.modules.project.model.Batch;
import com.cq.design.smartcost.modules.project.service.ProjectService;
import com.cq.design.smartcost.modules.raw.dao.FileHeaderDao;
import com.cq.design.smartcost.modules.raw.dao.FileItemDao;
import com.cq.design.smartcost.modules.raw.dao.FileRawDao;
import com.cq.design.smartcost.modules.raw.dto.MaterialFileView;
import com.cq.design.smartcost.modules.raw.model.FileHeader;
import com.cq.design.smartcost.modules.raw.model.FileItem;
import com.cq.design.smartcost.modules.raw.model.FileRaw;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 料表文件业务服务：批量上传料表文件到项目最新批次，按扩展名分发 PDF/Word 解析器，
 * 把封面写入 sc_file_header、原始行按顺序写入 sc_file_raw
 * （兼容设备表/材料表/名称规格表三种列布局，支持 .pdf/.doc/.docx）。
 */
@Service
public class RawMaterialFileService extends BusinessService {
    private static final Logger log = LoggerFactory.getLogger(RawMaterialFileService.class);

    @Resource(name = "projectService")
    private ProjectService projectService;
    @Resource(name = "batchDao")
    private BatchDao batchDao;
    @Resource(name = "fileService")
    private FileService fileService;
    @Resource(name = "fileInfoDao")
    private FileInfoDao fileInfoDao;
    @Resource(name = "fileHeaderDao")
    private FileHeaderDao fileHeaderDao;
    @Resource(name = "fileRawDao")
    private FileRawDao fileRawDao;
    @Resource(name = "fileItemDao")
    private FileItemDao fileItemDao;
    @Resource
    private MaterialTablePdfParser pdfParser;
    @Resource
    private MaterialTableWordParser wordParser;

    /**
     * 批量上传料表文件并同步解析：文件归属项目最新批次（文件来源-批次），
     * 并回填 sc_file.batch_no 便于列表展示与查询。
     * 任一文件解析失败即抛出业务异常，整个事务回滚（含已上传的其他文件），
     * 异常信息中指明解析出错的文件名。
     */
    public List<FileInfo> uploadAndParse(String projectId, List<MultipartFile> files) {
        if (files == null || files.isEmpty()) {
            throw new BusinessException("请选择要上传的料表文件");
        }
        Batch batch = currentBatch(projectId);
        List<FileInfo> results = new ArrayList<>();
        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }
            if (!isSupportedExtension(extensionOf(file.getOriginalFilename()))) {
                // 暂只实现 PDF/Word 解析，其他格式视为解析不成功，整体回滚。
                throw new BusinessException("料表解析暂仅支持 PDF/Word 格式：" + file.getOriginalFilename());
            }
            FileInfo info = fileService.upload(file, Constants.FileSource.BATCH,
                    batch.getId(), Constants.FileType.MATERIAL_TABLE);
            // sc_file.batch_no 记录所属批次号，通用上传不感知批次，这里补充回填。
            info.setBatchNo(batch.getBatchNo());
            fileInfoDao.updateById(info);
            try {
                parseAndSave(info);
            } catch (Exception exception) {
                log.error("料表解析失败，fileId={}", info.getId(), exception);
                // 登记记录将随事务回滚，物理文件需手动清理避免孤儿文件。
                fileService.deletePhysicalFile(info);
                throw new BusinessException("料表解析失败：" + info.getOriginalName());
            }
            results.add(info);
        }
        if (results.isEmpty()) {
            throw new BusinessException("请选择要上传的料表文件");
        }
        return results;
    }

    /**
     * 查询项目当前批次的料表文件列表（文件来源-批次），无批次时返回空列表。
     *
     * <p>每个文件附带分析状态：sc_file_item 中存在 file_id 关联数据视为“已分析”，否则“未分析”。</p>
     */
    public List<MaterialFileView> listByProject(String projectId) {
        Batch batch = latestBatch(projectId);
        if (batch == null) {
            return List.of();
        }
        List<FileInfo> files = fileService.list(Constants.FileSource.BATCH, batch.getId());
        if (files == null || files.isEmpty()) {
            return List.of();
        }
        // 一次 distinct 查询取 sc_file_item 中已有数据的文件 ID，避免逐文件计数。
        List<String> fileIds = files.stream().map(FileInfo::getId).toList();
        Set<String> analyzedIds = fileItemDao.selectObjs(new QueryWrapper<FileItem>()
                        .select("distinct file_id")
                        .in("file_id", fileIds)).stream()
                .map(String::valueOf)
                .collect(Collectors.toSet());
        return files.stream().map(info -> {
            MaterialFileView view = new MaterialFileView();
            view.setId(info.getId());
            view.setMasterType(info.getMasterType());
            view.setMasterId(info.getMasterId());
            view.setBatchNo(info.getBatchNo());
            view.setType(info.getType());
            view.setOriginalName(info.getOriginalName());
            view.setStoredName(info.getStoredName());
            view.setFilePath(info.getFilePath());
            view.setExtension(info.getExtension());
            view.setMimeType(info.getMimeType());
            view.setSize(info.getSize());
            view.setCreateUserId(info.getCreateUserId());
            view.setCreateOrgId(info.getCreateOrgId());
            view.setCreateDate(info.getCreateDate());
            view.setAnalyzed(analyzedIds.contains(info.getId()));
            return view;
        }).toList();
    }

    /**
     * 重新解析单个料表文件：先重新执行解析，成功后清除该文件的旧解析数据并写入新数据；
     * 解析或写入失败时抛出业务异常，整个事务回滚，旧解析数据保持不变。
     */
    public FileInfo reparse(String fileId) {
        FileInfo info = fileService.get(fileId);
        if (!isSupportedExtension(info.getExtension())) {
            throw new BusinessException("暂仅支持重新解析 PDF/Word 文件：" + info.getOriginalName());
        }
        try {
            parseAndSave(info);
        } catch (Exception exception) {
            log.error("料表重新解析失败，fileId={}", fileId, exception);
            throw new BusinessException("重新解析失败：" + info.getOriginalName());
        }
        return info;
    }

    /** 删除料表文件及其解析数据：先清表头与原始行，再删文件登记记录；物理文件在事务提交后清理。 */
    public void deleteMaterialFile(String fileId) {
        FileInfo info = fileService.get(fileId);
        fileHeaderDao.delete(new QueryWrapper<FileHeader>().eq("file_id", fileId));
        fileRawDao.delete(new QueryWrapper<FileRaw>().eq("file_id", fileId));
        fileService.delete(fileId);
    }

    /** 获取项目最新批次：无批次时先幂等初始化出第一批再返回。 */
    private Batch currentBatch(String projectId) {
        Batch batch = latestBatch(projectId);
        if (batch == null) {
            projectService.initialize(projectId);
            batch = latestBatch(projectId);
        }
        if (batch == null) {
            throw new BusinessException("项目批次初始化失败，请稍后重试");
        }
        return batch;
    }

    /** 查询项目最新批次（批次号最大），无批次时返回 null。 */
    private Batch latestBatch(String projectId) {
        return batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", projectId)
                .orderByDesc("batch_no")
                .last("LIMIT 1"));
    }

    /** 判断扩展名是否属于当前支持的料表解析格式（PDF 与 Word）。 */
    private boolean isSupportedExtension(String extension) {
        return "pdf".equalsIgnoreCase(extension)
                || "doc".equalsIgnoreCase(extension) || "docx".equalsIgnoreCase(extension);
    }

    /** 解析单个料表文件并落库表头与原始行；解析或写入异常直接向上抛出，由事务统一回滚。 */
    private void parseAndSave(FileInfo info) throws Exception {
        MaterialTableModels.ParsedTable parsed;
        String extension = info.getExtension() == null ? "" : info.getExtension();
        try (InputStream in = fileService.open(info)) {
            byte[] content = in.readAllBytes();
            parsed = "pdf".equalsIgnoreCase(extension)
                    ? pdfParser.parse(content) : wordParser.parse(content, extension);
        }
        // 支持后续重新解析：先清掉该文件旧的表头与原始行再写入。
        fileHeaderDao.delete(new QueryWrapper<FileHeader>().eq("file_id", info.getId()));
        fileRawDao.delete(new QueryWrapper<FileRaw>().eq("file_id", info.getId()));
        insertHeader(info, parsed);
        insertRawRows(info, parsed);
    }

    /** 写入表头解析结果：表类型暂存封面识别的原始标题，专业与工程名称来自封面。 */
    private void insertHeader(FileInfo info, MaterialTableModels.ParsedTable parsed) {
        FileHeader header = new FileHeader();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        header.setFileId(info.getId());
        header.setTableType(parsed.header.tableType);
        header.setSpecialtyName(parsed.header.specialty);
        header.setProjectSection(parsed.header.projectSection);
        fileHeaderDao.insert(header);
    }

    /** 按来源顺序写入原始行：所有列保存原始文本，空序号行同样保留（orderno 连续递增）。 */
    private void insertRawRows(FileInfo info, MaterialTableModels.ParsedTable parsed) {
        int orderno = 1;
        for (MaterialTableModels.ParsedRow row : parsed.rows) {
            FileRaw raw = new FileRaw();
            raw.setId(UUID.randomUUID().toString());
            raw.setFileId(info.getId());
            raw.setSerialNo(truncate(row.serialNo, 100));
            raw.setEquipmentTag(truncate(row.equipmentTag, 200));
            raw.setDescription(truncate(row.description, 2000));
            raw.setNominalSize(truncate(row.nominalSize, 500));
            raw.setUnit(truncate(row.unit, 100));
            raw.setQuantity(truncate(row.quantity, 500));
            raw.setUnitWeight(truncate(row.unitWeight, 100));
            raw.setTotalWeight(truncate(row.totalWeight, 100));
            raw.setRemark(truncate(row.remark, 2000));
            raw.setOrderno(orderno++);
            fileRawDao.insert(raw);
        }
    }

    /** 提取小写扩展名（不含点），无扩展名时返回空串。 */
    private String extensionOf(String originalName) {
        if (originalName == null) {
            return "";
        }
        int dotIndex = originalName.lastIndexOf('.');
        return dotIndex < 0 || dotIndex == originalName.length() - 1
                ? "" : originalName.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
    }

    /** 字符串按最大长度截断；null 或空串归一为 null，便于入库为空。 */
    private String truncate(String value, int maxLength) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }
}
