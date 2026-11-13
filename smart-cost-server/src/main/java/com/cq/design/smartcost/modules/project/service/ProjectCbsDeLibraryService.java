package com.cq.design.smartcost.modules.project.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.project.dao.ProjectCbsDao;
import com.cq.design.smartcost.modules.project.dao.ProjectCbsDeLibraryDao;
import com.cq.design.smartcost.modules.project.dto.ProjectCbsDeLibraryInput;
import com.cq.design.smartcost.modules.project.dto.ProjectCbsDeLibraryView;
import com.cq.design.smartcost.modules.project.model.ProjectCbs;
import com.cq.design.smartcost.modules.project.model.ProjectCbsDeLibrary;
import com.cq.design.smartcost.modules.quota.dao.DeLibraryDao;
import com.cq.design.smartcost.modules.quota.dto.QuotaLibraryView;
import com.cq.design.smartcost.modules.quota.model.DeLibrary;
import com.cq.design.smartcost.modules.quota.service.QuotaKnowledgeService;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.*;

/**
 * 项目 CBS 节点定额库挂载服务。
 *
 * <p>一个项目 CBS 节点可挂载多个定额库，关联记录存放在 sc_project_cbs_de_library。
 * 挂载与解挂均在事务内完成，重复挂载同一定额库时按已有记录跳过，不产生冗余数据。</p>
 */
@Service("projectCbsDeLibraryService")
public class ProjectCbsDeLibraryService extends BusinessService {
    /** 允许挂载定额库的结构分类名称。 */
    private static final String MOUNT_CATEGORY_NAME = "单位工程";

    @Resource(name = "projectCbsDao")
    private ProjectCbsDao projectCbsDao;
    @Resource(name = "projectCbsDeLibraryDao")
    private ProjectCbsDeLibraryDao projectCbsDeLibraryDao;
    @Resource(name = "deLibraryDao")
    private DeLibraryDao deLibraryDao;
    @Resource(name = "quotaKnowledgeService")
    private QuotaKnowledgeService quotaKnowledgeService;

    /**
     * 查询可供挂载的定额库列表。
     *
     * <p>复用定额知识库的服务能力，使项目构建页无需额外的定额知识库查看权限即可选择定额库。</p>
     */
    public List<QuotaLibraryView> libraryOptions() {
        return quotaKnowledgeService.libraries();
    }

    /**
     * 查询项目下所有 CBS 节点已挂载的定额库。
     *
     * @return 按项目 CBS 节点分组的定额库列表
     */
    public List<ProjectCbsDeLibraryView> listByProject(String projectId) {
        if (!StringUtils.hasText(projectId)) {
            throw new BusinessException("项目ID不能为空");
        }
        List<ProjectCbsDeLibrary> relations = projectCbsDeLibraryDao.selectList(
                new QueryWrapper<ProjectCbsDeLibrary>().eq("project_id", projectId));
        if (relations.isEmpty()) {
            return List.of();
        }
        // 批量取定额库，避免逐条查询。
        Set<String> libraryIds = new HashSet<>();
        for (ProjectCbsDeLibrary relation : relations) {
            if (StringUtils.hasText(relation.getDeLibraryId())) {
                libraryIds.add(relation.getDeLibraryId());
            }
        }
        Map<String, DeLibrary> libraryById = new HashMap<>();
        if (!libraryIds.isEmpty()) {
            for (DeLibrary library : deLibraryDao.selectByIds(libraryIds)) {
                libraryById.put(library.getId(), library);
            }
        }
        List<ProjectCbsDeLibraryView> result = new ArrayList<>();
        for (ProjectCbsDeLibrary relation : relations) {
            DeLibrary library = libraryById.get(relation.getDeLibraryId());
            if (library == null) {
                // 定额库已被删除的关联记录不再展示。
                continue;
            }
            ProjectCbsDeLibraryView view = new ProjectCbsDeLibraryView();
            view.setId(relation.getId());
            view.setProjectId(relation.getProjectId());
            view.setProjectCbsId(relation.getProjectCbsId());
            view.setDeLibraryId(library.getId());
            view.setDeLibraryCode(library.getCode());
            view.setDeLibraryName(library.getName());
            view.setDeLibraryType(library.getType());
            result.add(view);
        }
        return result;
    }

    /**
     * 为项目 CBS 节点挂载定额库。
     *
     * <p>同一节点可挂载多个定额库；已存在的关联直接跳过，重复提交不会产生冗余记录。</p>
     *
     * @return 本次新增的关联数量
     */
    public int mount(String projectId, ProjectCbsDeLibraryInput input) {
        ProjectCbs node = requireMountableNode(projectId, input.getProjectCbsId());
        List<String> libraryIds = input.getDeLibraryIds() == null ? List.of() : input.getDeLibraryIds();
        if (libraryIds.isEmpty()) {
            throw new BusinessException("请至少选择一个定额库");
        }
        // 校验定额库均存在。
        Set<String> distinctIds = new HashSet<>(libraryIds);
        List<DeLibrary> libraries = deLibraryDao.selectByIds(distinctIds);
        if (libraries.size() != distinctIds.size()) {
            throw new BusinessException("所选定额库不存在，请刷新后重试");
        }
        // 已有关联不重复写入。
        Set<String> existing = new HashSet<>();
        for (ProjectCbsDeLibrary relation : projectCbsDeLibraryDao.selectList(
                new QueryWrapper<ProjectCbsDeLibrary>()
                        .eq("project_id", projectId)
                        .eq("project_cbs_id", node.getId()))) {
            existing.add(relation.getDeLibraryId());
        }
        int created = 0;
        for (String libraryId : distinctIds) {
            if (existing.contains(libraryId)) {
                continue;
            }
            ProjectCbsDeLibrary relation = new ProjectCbsDeLibrary();
            // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
            relation.setProjectId(projectId);
            relation.setProjectCbsId(node.getId());
            relation.setDeLibraryId(libraryId);
            projectCbsDeLibraryDao.insert(relation);
            created++;
        }
        return created;
    }

    /**
     * 解挂项目 CBS 节点的定额库。
     *
     * @return 本次解除的关联数量
     */
    public int unmount(String projectId, String relationId) {
        if (!StringUtils.hasText(relationId)) {
            throw new BusinessException("请选择要解除挂载的定额库");
        }
        ProjectCbsDeLibrary relation = projectCbsDeLibraryDao.selectById(relationId);
        if (relation == null || !projectId.equals(relation.getProjectId())) {
            throw new BusinessException("挂载记录不存在");
        }
        projectCbsDeLibraryDao.deleteById(relationId);
        return 1;
    }

    /**
     * 校验目标节点存在、属于当前项目，且分类允许挂载定额库。
     */
    private ProjectCbs requireMountableNode(String projectId, String nodeId) {
        if (!StringUtils.hasText(nodeId)) {
            throw new BusinessException("请选择要挂载定额库的结构节点");
        }
        ProjectCbs node = projectCbsDao.selectById(nodeId);
        if (node == null || !projectId.equals(node.getProjectId())) {
            throw new BusinessException("所选结构节点不存在");
        }
        if (!MOUNT_CATEGORY_NAME.equals(node.getCategoryName())) {
            throw new BusinessException("只有“单位工程”节点允许挂载定额库");
        }
        return node;
    }
}
