package com.cq.design.smartcost.modules.ai.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.cq.design.smartcost.common.constants.Constants;
import com.cq.design.smartcost.common.time.TimestampText;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.ai.dao.AiPythonTaskDao;
import com.cq.design.smartcost.modules.ai.dto.AiPythonTaskView;
import com.cq.design.smartcost.modules.ai.model.AiPythonTask;
import com.cq.design.smartcost.modules.file.dao.FileInfoDao;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.project.dao.BatchDao;
import com.cq.design.smartcost.modules.project.dao.ProjectDao;
import com.cq.design.smartcost.modules.project.model.Batch;
import com.cq.design.smartcost.modules.project.model.Project;
import com.cq.design.smartcost.modules.raw.dto.QuantitySummary;
import com.cq.design.smartcost.modules.raw.service.QuantityStructureService;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * AI Python 任务服务：用户点击「下一步/重新构建」时往 sc_ai_python_task
 * 写入任务记录（status = 0 执行中），并把当前批次对应的 sc_file 状态
 * 置为该节点的"待处理"；Python 端轮询取任务并处理；
 * 前端轮询任务状态，status = 1（已生成）后取批次数据恢复操作。
 */
@Service
public class AiPythonTaskService {
    /** 任务状态：执行中。 */
    public static final String STATUS_RUNNING = "0";
    /** 任务状态：已生成（Python 端处理完成）。 */
    public static final String STATUS_DONE = "1";

    /**
     * 任务类型 → 批次文件待处理状态（sc_file.status）映射：
     * 0902 工程量编制 → 2101、0903 定额匹配 → 2103、0904 价格匹配 → 2105。
     * 创建任务时把批次下全部 sc_file 置为对应状态；非 AI 节点（如 0901）无映射不更新。
     */
    private static final Map<String, String> TASK_FILE_PENDING_STATUS = Map.of(
            Constants.CostingStage.QUANTITY_EDITING, Constants.AiFileStatus.QUANTITY_PENDING,
            Constants.CostingStage.QUOTA_MATCHING, Constants.AiFileStatus.QUOTA_PENDING,
            Constants.CostingStage.PRICE_MATCHING, Constants.AiFileStatus.PRICE_PENDING);

    @Resource(name = "aiPythonTaskDao")
    private AiPythonTaskDao aiPythonTaskDao;
    @Resource(name = "projectDao")
    private ProjectDao projectDao;
    @Resource(name = "batchDao")
    private BatchDao batchDao;
    @Resource(name = "fileInfoDao")
    private FileInfoDao fileInfoDao;
    @Resource(name = "quantityStructureService")
    private QuantityStructureService quantityStructureService;

    /**
     * 创建 AI 处理任务：写一条 status = 0 的任务记录供 Python 端认领；
     * 首次执行（hasError = false）时把批次下 sc_file 状态置为该节点的"待处理"。
     *
     * <p>重试语义：若同一项目 + 批次 + 任务类型下已存在「已生成但失败」
     * （status = 1 且 error_message 非空）的任务，则不再新增记录，
     * 直接把该任务重置为待执行（status = 0、error_message 清空、
     * request_id 换新并刷新创建时间），相当于重新发起一次。</p>
     *
     * @param projectId 项目 UUID
     * @param taskType  任务类型（组价节点编码，如 0902 工程量结构树构建）
     * @param hasError  当前任务类型的最新任务是否带错误信息（前端查询后传入）：
     *                  true 表示该任务已处理过一次（失败重试），sc_file 已处于
     *                  该节点的待处理状态，不再改动其 status；
     *                  false 表示首次执行，才全量重置 sc_file 状态
     * @return 任务视图
     */
    public AiPythonTaskView createTask(String projectId, String taskType, boolean hasError) {
        if (projectId == null || projectId.isBlank()) {
            throw new BusinessException("项目不能为空");
        }
        if (taskType == null || taskType.isBlank()) {
            throw new BusinessException("任务类型不能为空");
        }
        Project project = projectDao.selectById(projectId);
        if (project == null) {
            throw new BusinessException("项目不存在");
        }
        Batch batch = latestBatch(projectId);
        if (batch == null) {
            throw new BusinessException("项目批次不存在，请先完成初始化");
        }
        // 工程量编制 → 定额匹配（0903）前置校验：批次内还有未挂接数据时禁止创建任务，
        // AI 定额匹配依赖挂接结果，未挂接项没有归属节点无法匹配。
        if (Constants.CostingStage.QUOTA_MATCHING.equals(taskType)) {
            QuantitySummary quantitySummary = quantityStructureService.summary(projectId, batch.getId());
            if (quantitySummary.getUnattachedItems() > 0) {
                throw new BusinessException("还有 " + quantitySummary.getUnattachedItems()
                        + " 条未挂接的工程量数据，请先在工程量编制中完成挂接");
            }
        }

        AiPythonTask task = resetFailedTask(projectId, batch.getId(), taskType);
        if (task == null) {
            task = new AiPythonTask();
            // id、创建人、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
            task.setRequestId(UUID.randomUUID().toString());
            task.setProjectId(projectId);
            task.setBatchId(batch.getId());
            task.setTaskType(taskType);
            task.setStatus(STATUS_RUNNING);
            aiPythonTaskDao.insert(task);

        }
        // 带错误信息 = 已处理过一次的失败重试，sc_file 仍处于该节点的待处理状态，
        // 不再重复改动；只有首次执行才全量重置批次文件状态。
        if (!hasError) {
            markBatchFilesPending(batch, taskType);
        }
        return toView(task);
    }

    /**
     * 重置失败任务：同一项目 + 批次 + 任务类型下存在「status = 1 且
     * error_message 非空」的任务时，一条 UPDATE 批量重置为待执行
     * （status = 0、error_message 清空、request_id 换新、刷新创建时间）。
     *
     * @return 重置后的任务；不存在失败任务时返回 null
     */
    private AiPythonTask resetFailedTask(String projectId, String batchId, String taskType) {
        List<AiPythonTask> failed = aiPythonTaskDao.selectList(new QueryWrapper<AiPythonTask>()
                .eq("project_id", projectId)
                .eq("batch_id", batchId)
                .eq("task_type", taskType)
                .eq("status", STATUS_DONE)
                .isNotNull("error_message")
                .ne("error_message", "")
                .orderByDesc("create_date")
                .last("LIMIT 1"));
        if (failed.isEmpty()) {
            return null;
        }
        AiPythonTask task = failed.get(0);
        String newRequestId = UUID.randomUUID().toString();
        // 一条 UPDATE 批量重置，不逐行轮询更新。
        aiPythonTaskDao.update(null, new UpdateWrapper<AiPythonTask>()
                .eq("id", task.getId())
                .set("status", STATUS_RUNNING)
                .set("error_message", null)
                .set("request_id", newRequestId)
                .set("create_date", TimestampText.now()));
        task.setStatus(STATUS_RUNNING);
        task.setErrorMessage(null);
        task.setRequestId(newRequestId);
        task.setCreateDate(TimestampText.now());
        return task;
    }

    /** 把批次归属的全部 sc_file 状态置为任务类型对应的"待处理"状态（非 AI 节点跳过）。 */
    private void markBatchFilesPending(Batch batch, String taskType) {
        String pendingStatus = TASK_FILE_PENDING_STATUS.get(taskType);
        if (pendingStatus == null) {
            return;
        }
        // 一条 UPDATE 批量更新批次下全部料表状态，不做逐行轮询。
        fileInfoDao.update(null, new UpdateWrapper<FileInfo>()
                .eq("master_type", Constants.FileSource.BATCH)
                .eq("master_id", batch.getId())
                .set("status", pendingStatus));
    }

    /**
     * 查询项目最新一条 AI 任务（可按任务类型过滤），供前端轮询任务状态。
     *
     * <p>仅当任务「成功完成」（status = 1 且 error_message 为空）时，才把批次
     * 当前节点 {@code sc_batch.current_stage} 推进到任务对应的节点
     * （任务类型即目标节点编码，如 0902 任务完成 → 批次推进到 0902）。
     * status = 1 但 error_message 非空表示处理失败，不推进节点，由前端提示错误。
     * 推进幂等：批次已到达或已越过该节点时不重复更新、不回退，
     * 因此前端 20 秒一次的轮询重复查询是安全的。</p>
     *
     * @param projectId 项目 UUID
     * @param taskType  任务类型（组价节点编码），为空时不过滤
     * @return 最新任务视图；尚无任务时返回 null
     */
    public AiPythonTaskView latestTask(String projectId, String taskType) {
        QueryWrapper<AiPythonTask> wrapper = new QueryWrapper<AiPythonTask>()
                .eq("project_id", projectId);
        if (taskType != null && !taskType.isBlank()) {
            wrapper.eq("task_type", taskType);
        }
        List<AiPythonTask> tasks = aiPythonTaskDao.selectList(wrapper
                .orderByDesc("create_date")
                .last("LIMIT 1"));
        if (tasks.isEmpty()) {
            return null;
        }
        AiPythonTask task = tasks.get(0);
        if (STATUS_DONE.equals(task.getStatus())
                && (task.getErrorMessage() == null || task.getErrorMessage().isBlank())) {
            advanceBatchStage(projectId, task.getTaskType());
        }
        return toView(task);
    }

    /**
     * 任务完成后推进批次节点到任务对应节点（幂等）。
     * 组价节点编码（0901~0906）单调递增：目标大于当前才前进，
     * 相等说明已推进过、小于说明批次已越过该节点，均跳过。
     */
    private void advanceBatchStage(String projectId, String targetStage) {
        if (targetStage == null || targetStage.isBlank()) {
            return;
        }
        Batch batch = latestBatch(projectId);
        if (batch == null) {
            return;
        }
        String currentStage = batch.getCurrentStage();
        if (currentStage != null && targetStage.compareTo(currentStage) <= 0) {
            return;
        }
        batch.setCurrentStage(targetStage);
        batchDao.updateById(batch);
    }

    /** 项目最新批次（批次号最大）。 */
    private Batch latestBatch(String projectId) {
        return batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", projectId)
                .orderByDesc("batch_no")
                .last("LIMIT 1"));
    }

    private AiPythonTaskView toView(AiPythonTask task) {
        AiPythonTaskView view = new AiPythonTaskView();
        view.setId(task.getId());
        view.setRequestId(task.getRequestId());
        view.setProjectId(task.getProjectId());
        view.setBatchId(task.getBatchId());
        view.setTaskType(task.getTaskType());
        view.setStatus(task.getStatus());
        view.setErrorMessage(task.getErrorMessage());
        return view;
    }
}
