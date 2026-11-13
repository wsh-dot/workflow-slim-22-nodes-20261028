package com.cq.design.smartcost.modules.raw.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.cq.design.smartcost.common.constants.Constants;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.file.service.FileService;
import com.cq.design.smartcost.modules.project.dao.BatchDao;
import com.cq.design.smartcost.modules.project.model.Batch;
import com.cq.design.smartcost.modules.project.service.ProjectCbsService;
import com.cq.design.smartcost.modules.raw.dao.FileHeaderDao;
import com.cq.design.smartcost.modules.raw.dao.FileItemDao;
import com.cq.design.smartcost.modules.raw.dto.FileItemNodeView;
import com.cq.design.smartcost.modules.raw.dto.QuantityCbsNodeView;
import com.cq.design.smartcost.modules.raw.dto.QuantitySummary;
import com.cq.design.smartcost.modules.raw.model.FileHeader;
import com.cq.design.smartcost.modules.raw.model.FileItem;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 工程量编制业务服务：提供左侧 CBS 树（带挂接统计）、指定 CBS 底层节点的
 * 工程量列表、未挂接列表与汇总统计查询，以及手工挂接/取消挂接。
 *
 * <p>所有数据均按批次隔离：一个项目可有多个批次，每个批次的料表与挂接结果互不
 * 互通，因此全部接口都以批次 ID 为必传参数，工程量项的批次归属由其所属料表
 * （sc_file.master_id = 批次 ID）决定。</p>
 *
 * <p>工程量数据为线性结构（只含设备/主材），设备/主材分类展示由前端合成文件夹完成；
 * 数据由 Python 端处理 AI 任务后写入 sc_file_item，
 * 任务通过 {@code AiPythonTaskService} 创建与跟踪。</p>
 */
@Service
public class QuantityStructureService extends BusinessService {
    private static final Logger log = LoggerFactory.getLogger(QuantityStructureService.class);

    /** 单位工程分类名称：只有该分类节点被视为可挂接的单位工程。 */
    private static final String UNIT_PROJECT_CATEGORY = "单位工程";
    /**
     * 工程量编制只处理设备与主材两类数据（sc_file_item.type）：
     * 兼容英文别名与字典13编码两种写法。
     */
    private static final List<String> ITEM_TYPES = List.of(Constants.ItemNodeType.MAIN_MATERIAL,Constants.ItemNodeType.EQUIPMENT);

    private static final List<String> ITEM_PROCESSED = List.of(Constants.MatchStatus.MATCHED, Constants.MatchStatus.PROCESSED);

    @Resource(name = "projectCbsService")
    private ProjectCbsService projectCbsService;
    @Resource(name = "projectCbsDao")
    private com.cq.design.smartcost.modules.project.dao.ProjectCbsDao projectCbsDao;
    @Resource(name = "batchDao")
    private BatchDao batchDao;
    @Resource(name = "fileService")
    private FileService fileService;
    @Resource(name = "fileHeaderDao")
    private FileHeaderDao fileHeaderDao;
    @Resource(name = "fileItemDao")
    private FileItemDao fileItemDao;
    @Resource(name = "fileInfoDao")
    private com.cq.design.smartcost.modules.file.dao.FileInfoDao fileInfoDao;

    /** 工程量结构汇总统计（按批次）：结构项总数与未挂接数量。 */
    public QuantitySummary summary(String projectId, String batchId) {
        Batch batch = requireBatch(projectId, batchId);
        QuantitySummary summaryView = new QuantitySummary();
        List<FileItem> items = listBatchItems(batch);
        summaryView.setTotalItems(items.size());
        summaryView.setUnattachedItems(items.stream()
                .filter(item -> isUnattached(item.getProjectCbsId()))
                .count());
        return summaryView;
    }

    /** 左侧 CBS 树（按批次）：项目 CBS 结构 + 该批次下每个节点挂接的工程量数量。 */
    public List<QuantityCbsNodeView> cbsTree(String projectId, String batchId) {
        Batch batch = requireBatch(projectId, batchId);
        Map<String, Long> countByCbs = new HashMap<>();
        for (FileItem item : listBatchItems(batch)) {
            if (!isUnattached(item.getProjectCbsId())) {
                countByCbs.merge(item.getProjectCbsId(), 1L, Long::sum);
            }
        }
        return toQuantityTree(projectCbsService.tree(batch.getProjectId()), countByCbs);
    }

    /**
     * 指定批次下挂到某 CBS 最底层节点的工程量列表（线性结构，只取设备/主材；
     * 设备/主材分类展示由前端合成文件夹完成）。
     */
    public List<FileItemNodeView> itemsByCbs(String cbsId, String batchId) {
        List<FileInfo> files = listBatchFiles(batchId);
        if (files.isEmpty()) {
            return List.of();
        }
        List<FileItem> items = fileItemDao.selectList(new QueryWrapper<FileItem>()
                .in("file_id", files.stream().map(FileInfo::getId).toList())
                .eq("project_cbs_id", cbsId)
                .in("cbs_match_status",ITEM_PROCESSED)
                .in("type", ITEM_TYPES)
                .orderByAsc("sort_no"));
        List<FileItemNodeView> views = new ArrayList<>();
        for (FileItem item : items) {
            views.add(toItemView(item));
        }
        return views;
    }

    /**
     * 未挂接工程量列表（供“未挂接”页签展示，按批次）。
     *
     * <p>线性结构，只取该批次下未挂接的设备/主材末级项（设备/主材分类展示由前端
     * 合成文件夹完成，不入库）；回填料表标题、专业与来源描述。</p>
     */
    public List<FileItemNodeView> unattachedList(String projectId, String batchId) {
        List<FileInfo> files = listBatchFiles(requireBatch(projectId, batchId).getId());
        if (files.isEmpty()) {
            return List.of();
        }
        List<String> fileIds = files.stream().map(FileInfo::getId).toList();
        List<FileItem> items = fileItemDao.selectList(new QueryWrapper<FileItem>()
                .in("file_id", fileIds)
                .eq("cbs_match_status", Constants.MatchStatus.UNMATCHED)
                .in("type", ITEM_TYPES)
                .orderByAsc("file_id")
                .orderByAsc("sort_no"));
        if (items.isEmpty()) {
            return List.of();
        }
        Map<String, FileInfo> fileMap = new HashMap<>();
        for (FileInfo info : files) {
            fileMap.put(info.getId(), info);
        }
        Map<String, FileHeader> headerMap = new HashMap<>();
        for (FileHeader header : fileHeaderDao.selectList(new QueryWrapper<FileHeader>().in("file_id", fileIds))) {
            headerMap.putIfAbsent(header.getFileId(), header);
        }

        // 只保留未挂接的末级项，并按文件内出现顺序回填来源信息。
        List<FileItemNodeView> result = new ArrayList<>();
        Map<String, Integer> ordinalByFile = new HashMap<>();
        for (FileItem item : items) {
            if (!isUnattached(item.getProjectCbsId())) {
                continue;
            }
            FileItemNodeView view = toItemView(item);
            FileInfo file = fileMap.get(view.getFileId());
            FileHeader header = headerMap.get(view.getFileId());
            view.setSpecialty(header == null ? null : blankToNull(header.getSpecialtyName()));
            view.setFileTitle(composeFileTitle(file, header));
            String fileName = file == null ? "" : stripExtension(file.getOriginalName());
            int ordinal = ordinalByFile.merge(view.getFileId() == null ? "" : view.getFileId(), 1, Integer::sum);
            view.setSource(fileName + " / 第" + ordinal + "项");
            result.add(view);
        }
        return result;
    }

    /**
     * 手工挂接（按批次）：把该批次下的单个工程量项挂到指定 CBS 最底层节点。
     *
     * @return 挂接后的汇总统计（同批次）
     */
    public QuantitySummary attach(String itemId, String cbsId, String batchId) {
        Batch batch = requireBatch(batchId);
        FileItem item = requireBatchItem(itemId, batch);
        com.cq.design.smartcost.modules.project.model.ProjectCbs cbs =
                projectCbsDao.selectById(cbsId);
        if (cbs == null) {
            throw new BusinessException("CBS 节点不存在");
        }
        if (!batch.getProjectId().equals(cbs.getProjectId())) {
            throw new BusinessException("CBS 节点不属于该批次所属项目");
        }
        // 挂接目标：单位工程（场站，倒数第二层）节点，或无下级的最底层节点。
        boolean unitProject = UNIT_PROJECT_CATEGORY.equals(cbs.getCategoryName());
        if (!unitProject) {
            Long childCount = projectCbsDao.selectCount(new QueryWrapper<com.cq.design.smartcost.modules.project.model.ProjectCbs>()
                    .eq("parent_id", cbsId));
            if (childCount != null && childCount > 0) {
                throw new BusinessException("请选择场站（单位工程）节点或 CBS 最底层节点");
            }
        }
        if (!isUnattached(item.getProjectCbsId())) {
            throw new BusinessException("该工程量项已挂接，请刷新后重试");
        }
        item.setProjectCbsId(cbsId);
        item.setCbsMatchStatus(Constants.MatchStatus.PROCESSED);
        item.setCbsMatchMethod(Constants.MatchMethod.MANUAL);
        fileItemDao.updateById(item);
        log.info("手工挂接工程量项：batchId={}, itemId={}, cbsId={}", batchId, itemId, cbsId);
        return summary(batch.getProjectId(), batchId);
    }

    /**
     * 批量挂接（按批次）：把某张料表下全部未挂接的设备/主材一次性挂到指定 CBS 节点。
     * 与单体挂接同一套校验（批次归属、CBS 节点合法性），挂接方式记为人工；
     * 已挂接的明细保持原状，仅处理未挂接项。
     *
     * @return 挂接后的汇总统计（同批次）
     */
    public QuantitySummary attachByFile(String fileId, String cbsId, String batchId) {
        Batch batch = requireBatch(batchId);
        FileInfo file = fileInfoDao.selectById(fileId);
        if (file == null || !Constants.FileSource.BATCH.equals(file.getMasterType())
                || !batch.getId().equals(file.getMasterId())) {
            throw new BusinessException("料表不存在或不属于当前批次，请刷新后重试");
        }
        com.cq.design.smartcost.modules.project.model.ProjectCbs cbs =
                projectCbsDao.selectById(cbsId);
        if (cbs == null) {
            throw new BusinessException("CBS 节点不存在");
        }
        if (!batch.getProjectId().equals(cbs.getProjectId())) {
            throw new BusinessException("CBS 节点不属于该批次所属项目");
        }
        // 挂接目标：单位工程（场站，倒数第二层）节点，或无下级的最底层节点（与单体挂接一致）。
        boolean unitProject = UNIT_PROJECT_CATEGORY.equals(cbs.getCategoryName());
        if (!unitProject) {
            Long childCount = projectCbsDao.selectCount(new QueryWrapper<com.cq.design.smartcost.modules.project.model.ProjectCbs>()
                    .eq("parent_id", cbsId));
            if (childCount != null && childCount > 0) {
                throw new BusinessException("请选择场站（单位工程）节点或 CBS 最底层节点");
            }
        }
        Long pending = fileItemDao.selectCount(new QueryWrapper<FileItem>()
                .eq("file_id", fileId)
                .isNull("project_cbs_id")
                .in("type", ITEM_TYPES));
        if (pending == null || pending == 0) {
            throw new BusinessException("该料表下没有未挂接的设备/主材明细");
        }
        fileItemDao.update(null, new UpdateWrapper<FileItem>()
                .eq("file_id", fileId)
                .isNull("project_cbs_id")
                .in("type", ITEM_TYPES)
                .set("project_cbs_id", cbsId)
                .set("cbs_match_status", Constants.MatchStatus.PROCESSED)
                .set("cbs_match_method", Constants.MatchMethod.MANUAL));
        log.info("批量挂接料表工程量项：batchId={}, fileId={}, cbsId={}, count={}",
                batchId, fileId, cbsId, pending);
        return summary(batch.getProjectId(), batchId);
    }

    /**
     * 取消挂接（按批次）：把已挂接的工程量项恢复为未挂接，允许用户重新挂接。
     *
     * <p>取消后 cbs_match_status 置为未命中（1402）、cbs_match_method 置为人工（1502），
     * 挂接目标清空。</p>
     *
     * @return 取消挂接后的汇总统计（同批次）
     */
    public QuantitySummary detach(String itemId, String batchId) {
        Batch batch = requireBatch(batchId);
        FileItem item = requireBatchItem(itemId, batch);
        if (isUnattached(item.getProjectCbsId())) {
            throw new BusinessException("该工程量项未挂接，无需取消");
        }
        com.cq.design.smartcost.modules.project.model.ProjectCbs cbs =
                projectCbsDao.selectById(item.getProjectCbsId());
        // updateById 默认忽略 null 字段（NOT_NULL 策略），置空 project_cbs_id 必须用
        // UpdateWrapper 显式 set null，否则库里仍保留旧挂接目标导致该项"假挂接"。
        fileItemDao.update(null, new UpdateWrapper<FileItem>()
                .eq("id", item.getId())
                .set("project_cbs_id", null)
                .set("cbs_match_status", Constants.MatchStatus.UNMATCHED)
                .set("cbs_match_method", Constants.MatchMethod.MANUAL));
        log.info("取消挂接工程量项：batchId={}, itemId={}, 原 cbsId={}",
                batchId, itemId, cbs == null ? "未知" : cbs.getId());
        return summary(batch.getProjectId(), batchId);
    }

    /** 校验批次存在，用于挂接/取消挂接等只有批次 ID 的写入操作。 */
    private Batch requireBatch(String batchId) {
        Batch batch = batchDao.selectById(batchId);
        if (batch == null) {
            throw new BusinessException("批次不存在或已被删除，请刷新后重试");
        }
        return batch;
    }

    /** 校验批次存在且归属指定项目，用于批次维度的查询。 */
    private Batch requireBatch(String projectId, String batchId) {
        Batch batch = requireBatch(batchId);
        if (!batch.getProjectId().equals(projectId)) {
            throw new BusinessException("批次不属于当前项目");
        }
        return batch;
    }

    /** 校验工程量项存在且属于指定批次（通过其所属料表的 master_id 判断）。 */
    private FileItem requireBatchItem(String itemId, Batch batch) {
        FileItem item = fileItemDao.selectById(itemId);
        if (item == null) {
            throw new BusinessException("工程量项不存在或已被重建，请刷新后重试");
        }
        FileInfo file = item.getFileId() == null ? null : fileInfoDao.selectById(item.getFileId());
        if (file == null || !Constants.FileSource.BATCH.equals(file.getMasterType())
                || !batch.getId().equals(file.getMasterId())) {
            throw new BusinessException("该工程量项不属于当前批次，请刷新后重试");
        }
        return item;
    }

    /** 查询批次下挂到指定工程的全部工程量结构项（只取设备/主材，供统计与挂接数）。 */
    private List<FileItem> listBatchItems(Batch batch) {
        List<FileInfo> files = listBatchFiles(batch.getId());
        if (files.isEmpty()) {
            return List.of();
        }
        return fileItemDao.selectList(new QueryWrapper<FileItem>()
                .in("file_id", files.stream().map(FileInfo::getId).toList())
                .in("type", ITEM_TYPES)
                .orderByAsc("sort_no"));
    }

    /** 查询批次归属的料表文件列表。 */
    private List<FileInfo> listBatchFiles(String batchId) {
        List<FileInfo> files = fileService.list(Constants.FileSource.BATCH, batchId);
        return files == null ? List.of() : files;
    }

    /** 分组节点的料表标题：优先表头工程路径，否则文件名（去扩展名）。 */
    private String composeFileTitle(FileInfo file, FileHeader header) {
        if (header != null && blankToNull(header.getProjectSection()) != null) {
            return header.getProjectSection().trim();
        }
        return file == null ? null : stripExtension(file.getOriginalName());
    }

    private String stripExtension(String name) {
        if (name == null) {
            return null;
        }
        int dot = name.lastIndexOf('.');
        return dot <= 0 ? name : name.substring(0, dot);
    }

    private String blankToNull(String text) {
        return text == null || text.isBlank() ? null : text.trim();
    }

    private boolean isUnattached(String projectCbsId) {
        return projectCbsId == null || projectCbsId.isEmpty();
    }

    /** 项目 CBS 视图树转工程量编制树并回填挂接数量。 */
    private List<QuantityCbsNodeView> toQuantityTree(
            List<com.cq.design.smartcost.modules.project.dto.ProjectCbsNodeView> tree, Map<String, Long> countByCbs) {
        List<QuantityCbsNodeView> result = new ArrayList<>();
        for (com.cq.design.smartcost.modules.project.dto.ProjectCbsNodeView node : tree) {
            QuantityCbsNodeView view = new QuantityCbsNodeView();
            view.setId(node.getId());
            view.setParentId(node.getParentId());
            view.setCode(node.getCode());
            view.setName(node.getName());
            view.setCategoryCode(node.getCategoryCode());
            view.setCategoryName(node.getCategoryName());
            view.setSortNo(node.getSortNo());
            view.setInnerCode(node.getInnerCode());
            view.getChildren().addAll(toQuantityTree(node.getChildren(), countByCbs));
            view.setItemCount(countByCbs.getOrDefault(node.getId(), 0L).intValue());
            result.add(view);
        }
        return result;
    }

    private FileItemNodeView toItemView(FileItem item) {
        FileItemNodeView view = new FileItemNodeView();
        view.setId(item.getId());
        view.setFileId(item.getFileId());
        view.setParentId(item.getParentId());
        view.setSortNo(item.getSortNo());
        view.setType(item.getType());
        view.setCode(item.getCode());
        view.setName(item.getName());
        view.setSpecification(item.getSpecification());
        view.setUnit(item.getUnit());
        view.setQuantity(item.getQuantity() == null ? null : item.getQuantity().toPlainString());
        view.setRemark(item.getRemark());
        view.setCbsMatchStatus(item.getCbsMatchStatus());
        view.setCbsMatchMethod(item.getCbsMatchMethod());
        view.setProjectCbsId(item.getProjectCbsId());
        return view;
    }
}
