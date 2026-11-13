package com.cq.design.smartcost.modules.project.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cq.design.smartcost.common.constants.Constants;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.service.PageSupport;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.common.web.PageResult;
import com.cq.design.smartcost.modules.project.dao.BatchDao;
import com.cq.design.smartcost.modules.project.dao.ProjectCbsDao;
import com.cq.design.smartcost.modules.project.dao.ProjectDao;
import com.cq.design.smartcost.modules.project.dao.ProjectFileDao;
import com.cq.design.smartcost.modules.project.dto.*;
import com.cq.design.smartcost.modules.project.model.Batch;
import com.cq.design.smartcost.modules.project.model.Project;
import com.cq.design.smartcost.modules.project.model.ProjectCbs;
import com.cq.design.smartcost.modules.project.model.ProjectFile;
import com.cq.design.smartcost.system.dao.OrganizationDao;
import com.cq.design.smartcost.system.dao.UserDao;
import com.cq.design.smartcost.system.model.SystemOrganization;
import com.cq.design.smartcost.system.model.SystemUser;
import jakarta.annotation.Resource;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/** 项目业务服务：项目主表的查询、新增、修改与删除校验。 */
@Service
public class ProjectService extends BusinessService {

    @Resource(name = "projectDao")
    private ProjectDao dao;
    @Resource(name = "batchDao")
    private BatchDao batchDao;
    @Resource(name = "projectCbsDao")
    private ProjectCbsDao projectCbsDao;
    @Resource(name = "projectCbsService")
    private ProjectCbsService projectCbsService;
    @Resource(name = "projectFileDao")
    private ProjectFileDao projectFileDao;
    @Resource(name = "userDao")
    private UserDao userDao;
    @Resource(name = "organizationDao")
    private OrganizationDao organizationDao;

    /**
     * 分页查询项目列表，关键字模糊匹配编码或名称，并补充审计字段名称。
     * 仅返回编制中（status = 0701）的项目；已完成（0702）等状态后续单独管理。
     */
    public PageResult<ProjectView> list(ProjectQueryInput input) {
        QueryWrapper<Project> query = new QueryWrapper<>();
        query.eq("status", Constants.ProjectStatus.EDITING);
        if (StringUtils.hasText(input.getKeyword())) {
            String keyword = input.getKeyword().trim();
            query.and(item -> item.like("code", keyword).or().like("name", keyword));
        }
        PageResult<Project> page = PageSupport.select(dao, query,
                input.getPage() == null ? 1 : input.getPage(),
                input.getSize() == null ? 20 : input.getSize(), true, "create_date");
        return toViews(page.getRecords(), page.getTotal(), page.getPage(), page.getSize());
    }

    /** 按主键查询单个项目详情，同样补充审计字段名称。 */
    public ProjectView get(String id) {
        Project current = dao.selectById(id);
        if (current == null) {
            throw new BusinessException("项目不存在");
        }
        return toViews(List.of(current), 1, 1, 1).getRecords().get(0);
    }

    /**
     * 初始化项目基础数据：创建默认批次与 CBS 根节点。
     *
     * <p>该操作幂等：默认批次或 CBS 根节点已存在时直接复用，不重复创建，
     * 供设计说明文件上传成功后调用。</p>
     */
    public ProjectInitResult initialize(String id) {
        Project project = get(id);
        ProjectInitResult result = new ProjectInitResult();
        result.setProjectId(project.getId());

        Batch batch = batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", project.getId())
                .orderByAsc("batch_no")
                .last("LIMIT 1"));
        if (batch == null) {
            batch = new Batch();
            // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
            batch.setProjectId(project.getId());
            batch.setBatchNo(nextBatchNo(project.getId()));
            // 批次初始状态与处理节点均取字典编码：批次状态-编制中(0801)、组价节点-CBS编制(0901，第一个节点)。
            batch.setStatus(Constants.BatchStatus.EDITING);
            batch.setCurrentStage(Constants.CostingStage.CBS_EDITING);
            batchDao.insert(batch);
            result.setBatchCreated(true);
        }
        result.setBatchId(batch.getId());
        result.setBatchNo(batch.getBatchNo());

        // CBS 根节点：不存在时按项目名称创建，已存在则直接复用。
        ProjectCbs root = projectCbsDao.selectOne(new QueryWrapper<ProjectCbs>()
                .eq("project_id", project.getId())
                .isNull("parent_id")
                .orderByAsc("sort_no")
                .last("LIMIT 1"));
        if (root == null) {
            root = projectCbsService.ensureCbsRoot(project.getId());
            result.setCbsRootCreated(true);
        }
        result.setCbsRootId(root.getId());
        result.setCbsRootName(root.getName());
        return result;
    }

    /** 查询项目最新批次（批次号最大）：无批次时返回 null，供前端按 currentStage 控制流程交互。 */
    public BatchView getCurrentBatch(String projectId) {
        Batch batch = batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", projectId)
                .orderByDesc("batch_no")
                .last("LIMIT 1"));
        if (batch == null) {
            return null;
        }
        BatchView view = new BatchView();
        view.setId(batch.getId());
        view.setBatchNo(batch.getBatchNo());
        view.setStatus(batch.getStatus());
        view.setCurrentStage(batch.getCurrentStage());
        return view;
    }

    /**
     * 推进批次当前组价节点（流程「下一步」）：更新最新批次的 current_stage。
     * 只允许在字典节点顺序内前进，不允许回退（重新构建不改变批次节点）。
     */
    public BatchView advanceStage(String projectId, String stage) {
        if (!StringUtils.hasText(stage)) {
            throw new BusinessException("组价节点不能为空");
        }
        Batch batch = batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", projectId)
                .orderByDesc("batch_no")
                .last("LIMIT 1"));
        if (batch == null) {
            throw new BusinessException("项目批次不存在");
        }
        batch.setCurrentStage(stage);
        batchDao.updateById(batch);
        BatchView view = new BatchView();
        view.setId(batch.getId());
        view.setBatchNo(batch.getBatchNo());
        view.setStatus(batch.getStatus());
        view.setCurrentStage(batch.getCurrentStage());
        return view;
    }

    /** 计算项目下一个批次号：取已有最大批次号加一，无批次时为 1。 */
    private int nextBatchNo(String projectId) {
        Batch latest = batchDao.selectOne(new QueryWrapper<Batch>()
                .eq("project_id", projectId)
                .orderByDesc("batch_no")
                .last("LIMIT 1"));
        return latest == null || latest.getBatchNo() == null ? 1 : latest.getBatchNo() + 1;
    }

    /** 将项目实体集合转换为视图并批量填充创建人姓名与机构名称，避免逐行查询。 */
    private PageResult<ProjectView> toViews(List<Project> records, long total, int page, int size) {
        Set<String> userIds = records.stream().map(Project::getCreateUserId)
                .filter(StringUtils::hasText).collect(Collectors.toSet());
        Set<String> orgIds = records.stream().map(Project::getCreateOrgId)
                .filter(StringUtils::hasText).collect(Collectors.toSet());
        Map<String, String> userNames = userIds.isEmpty() ? Map.of()
                : userDao.selectByIds(userIds).stream()
                        .filter(user -> user.getDeleteStatus() == null || user.getDeleteStatus() == 0)
                        .collect(Collectors.toMap(SystemUser::getId, SystemUser::getName, (a, b) -> a));
        Map<String, String> orgNames = orgIds.isEmpty() ? Map.of()
                : organizationDao.selectByIds(orgIds).stream()
                        .filter(org -> org.getDeleteStatus() == null || org.getDeleteStatus() == 0)
                        .collect(Collectors.toMap(SystemOrganization::getId, SystemOrganization::getName, (a, b) -> a));
        List<ProjectView> views = records.stream().map(project -> {
            ProjectView view = new ProjectView();
            BeanUtils.copyProperties(project, view);
            view.setCreateUserName(userNames.get(project.getCreateUserId()));
            view.setCreateOrgName(orgNames.get(project.getCreateOrgId()));
            return view;
        }).collect(Collectors.toList());
        return new PageResult<>(views, total, page, size);
    }

    /** 新增项目，项目编码全库唯一。 */
    public ProjectView create(ProjectInput input) {
        if (dao.selectCount(new QueryWrapper<Project>().eq("code", input.getCode())) > 0) {
            throw new BusinessException("项目编码已存在");
        }
        Project project = new Project();
        // DTO 与实体的同名字段统一用 BeanUtils 映射，避免逐字段 set 遗漏。
        BeanUtils.copyProperties(input, project);
        project.setStatus(Constants.ProjectStatus.EDITING);
        // 创建人、机构、创建时间与主键由 UuidIdMetaObjectHandler 在插入时自动填充，不信任前端传入。
        dao.insert(project);
        return toViews(List.of(project), 1, 1, 1).getRecords().get(0);
    }

    /** 修改项目资料，项目编码唯一且不得与他人冲突。 */
    public ProjectView update(String id, ProjectInput input) {
        Project current = get(id);
        // 唯一性校验排除自身，避免修改其他字段时被编码冲突拦截。
        Long sameCode = dao.selectCount(new QueryWrapper<Project>()
                .eq("code", input.getCode()).ne("id", id));
        if (sameCode != null && sameCode > 0) {
            throw new BusinessException("项目编码已存在");
        }
        // DTO 与实体同名字段统一用 BeanUtils 映射，主键与审计字段不来自输入。
        BeanUtils.copyProperties(input, current);
        dao.updateById(current);
        return toViews(List.of(current), 1, 1, 1).getRecords().get(0);
    }

    /** 删除项目；存在批次、项目 CBS 节点或项目文件时禁止删除。 */
    public void delete(String id) {
        Project current = get(id);
        if (batchDao.selectCount(new QueryWrapper<Batch>().eq("project_id", id)) > 0) {
            throw new BusinessException("请先删除项目下的批次");
        }
        if (projectCbsDao.selectCount(new QueryWrapper<ProjectCbs>().eq("project_id", id)) > 0) {
            throw new BusinessException("请先删除项目的 CBS 结构");
        }
        if (projectFileDao.selectCount(new QueryWrapper<ProjectFile>()
                // 项目文件按字典"文件来源-项目"(1001) 归属校验，与上传时的 masterType 保持一致。
                .eq("master_type", Constants.FileSource.PROJECT).eq("master_id", id)) > 0) {
            throw new BusinessException("请先删除项目下的文件");
        }
        dao.deleteById(current.getId());
    }
}
