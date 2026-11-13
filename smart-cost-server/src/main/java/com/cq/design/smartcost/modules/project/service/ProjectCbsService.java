package com.cq.design.smartcost.modules.project.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.cbs.dto.CbsDetailInfo;
import com.cq.design.smartcost.modules.cbs.dto.CbsDetailNode;
import com.cq.design.smartcost.modules.cbs.dto.CbsTemplateView;
import com.cq.design.smartcost.modules.cbs.service.CbsTemplateService;
import com.cq.design.smartcost.modules.project.dao.ProjectCbsDao;
import com.cq.design.smartcost.modules.project.dao.ProjectCbsDeLibraryDao;
import com.cq.design.smartcost.modules.project.dao.ProjectDao;
import com.cq.design.smartcost.modules.project.dto.*;
import com.cq.design.smartcost.modules.project.model.Project;
import com.cq.design.smartcost.modules.project.model.ProjectCbs;
import com.cq.design.smartcost.modules.project.model.ProjectCbsDeLibrary;
import com.cq.design.smartcost.modules.raw.dao.FileItemDao;
import com.cq.design.smartcost.modules.raw.model.FileItem;
import jakarta.annotation.Resource;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.*;

/**
 * 项目 CBS 服务：项目结构树的查询，以及把平台标准结构引入项目。
 *
 * <p>每次引入都是独立的一份：同一批标准节点可以重复引入，生成互不影响的新记录，
 * 不与既有节点合并，也不复用历史记录。</p>
 *
 * <p>所有结构操作（引入、新增、删除、复制、移动、改名）均由服务端在事务内完成，
 * 并递归重算受影响子树的 sort_no 与 inner_code，保证层级与排序始终自洽。</p>
 */
@Service
public class ProjectCbsService extends BusinessService {
    /** 项目 CBS 根节点的层级路径码。 */
    private static final String CBS_ROOT_INNER_CODE = "1";
    /** 层级路径码的分隔符，与平台标准结构保持一致。 */
    private static final String INNER_CODE_SEPARATOR = ".";
    /** 上移：在同级中上移一位。 */
    private static final String DIRECTION_UP = "UP";
    /** 下移：在同级中下移一位。 */
    private static final String DIRECTION_DOWN = "DOWN";
    /** 升级：变为父节点的同级节点。 */
    private static final String DIRECTION_PROMOTE = "PROMOTE";
    /** 降级：变为前一个兄弟节点的子节点。 */
    private static final String DIRECTION_DEMOTE = "DEMOTE";
    /** 最末级结构分类，其下不允许再降级挂载子节点。 */
    private static final String LOWEST_CATEGORY_NAME = "单位工程";

    @Resource(name = "projectDao")
    private ProjectDao projectDao;
    @Resource(name = "projectCbsDao")
    private ProjectCbsDao projectCbsDao;
    @Resource(name = "projectCbsDeLibraryDao")
    private ProjectCbsDeLibraryDao projectCbsDeLibraryDao;
    @Resource(name = "cbsTemplateService")
    private CbsTemplateService cbsTemplateService;
    @Resource(name = "fileItemDao")
    private FileItemDao fileItemDao;

    /** 查询项目 CBS 树，按 parent_id 还原层级。 */
    public List<ProjectCbsNodeView> tree(String projectId) {
        if (!StringUtils.hasText(projectId)) {
            throw new BusinessException("项目ID不能为空");
        }
        List<ProjectCbs> nodes = projectCbsDao.selectList(new QueryWrapper<ProjectCbs>()
                .eq("project_id", projectId)
                .orderByAsc("sort_no"));
        return buildTree(nodes);
    }

    /**
     * 把平台标准结构引入项目 CBS。
     *
     * <p>服务端不采信前端提交的层级关系：只接收「用户明确勾选的明细 ID 集合」与「级联标志」，
     * 重新查询平台模板树后自行计算最终引入的节点集合，并按标准层级重新生成项目内的父子关系。</p>
     *
     * <p>级联为是时自动关联所选节点的父节点与全部子节点；为否时只引入明确勾选的节点，
     * 未勾选的中间层被跳过、其下已勾选分支提升为上一级。</p>
     */
    public ProjectCbsImportResult importFromStandard(ProjectCbsImportInput input) {
        Project project = projectDao.selectById(input.getProjectId());
        if (project == null) {
            throw new BusinessException("项目不存在");
        }
        List<String> detailIds = input.getDetailIds().stream()
                .filter(StringUtils::hasText).distinct().toList();
        if (detailIds.isEmpty()) {
            throw new BusinessException("请先选择要增加的标准结构");
        }
        List<CbsDetailInfo> details = cbsTemplateService.listDetailsByIds(detailIds);
        if (details.isEmpty()) {
            throw new BusinessException("所选标准结构不存在");
        }
        String cbsId = details.get(0).getCbsId();
        for (CbsDetailInfo detail : details) {
            if (!cbsId.equals(detail.getCbsId())) {
                throw new BusinessException("不能同时引入不同CBS模板的结构");
            }
        }
        CbsTemplateView template = cbsTemplateService.getTemplate(cbsId);

        // 重新查询平台模板树，自行计算最终引入的节点集合，不使用前端传来的层级关系。
        List<CbsDetailNode> templateRoots = cbsTemplateService.templateTree(cbsId);
        TemplateIndex index = indexTemplate(templateRoots);
        for (String detailId : detailIds) {
            if (!index.nodeById().containsKey(detailId)) {
                throw new BusinessException("所选标准结构已变更，请刷新后重试");
            }
        }
        boolean cascade = !Boolean.FALSE.equals(input.getCascade());
        Set<String> finalIds = resolveFinalIds(detailIds, input.getExcludedDetailIds(), cascade, index);

        // 平台模板的最顶层节点只是容器，引入时只取其下的分支。
        List<CbsDetailNode> branches = new ArrayList<>();
        for (CbsDetailNode root : templateRoots) {
            branches.addAll(prune(root.getChildren(), finalIds));
        }
        if (branches.isEmpty()) {
            throw new BusinessException("没有可增加的结构节点");
        }

        TargetPosition position = resolveTargetPosition(input.getProjectId(), input.getTargetNodeId());
        // 为待写入的分支腾出连续的排序号，后续同级节点整体后移。
        reserveSortNos(input.getProjectId(), position.parent(), position.sortNo(), branches.size());
        List<String> rootIds = new ArrayList<>();
        int total = 0;
        int sortNo = position.sortNo();
        for (CbsDetailNode branch : branches) {
            ProjectCbs created = insertNode(branch, project.getId(), position.parent(), template, sortNo++);
            rootIds.add(created.getId());
            total++;
            total += insertChildren(branch, project.getId(), created, template);
        }
        rebuildChildren(position.parent());
        ProjectCbsImportResult result = new ProjectCbsImportResult();
        result.setProjectId(project.getId());
        result.setRootIds(rootIds);
        result.setTotalCount(total);
        result.setCbsRootId(position.parent().getId());
        return result;
    }

    /**
     * 在选中节点下新增一个自建节点。
     *
     * <p>挂接位置由服务端按规则推导：未选中时挂到项目根节点下；选中非叶子节点时挂到该节点下；
     * 选中叶子节点时挂到该叶子节点的父节点下作为同级节点。</p>
     *
     * @return 新建节点的 UUID
     */
    public String createNode(String projectId, ProjectCbsNodeInput input) {
        if (projectDao.selectById(projectId) == null) {
            throw new BusinessException("项目不存在");
        }
        TargetPosition position = resolveTargetPosition(projectId, input.getTargetNodeId());
        reserveSortNos(projectId, position.parent(), position.sortNo(), 1);
        ProjectCbs node = new ProjectCbs();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        node.setProjectId(projectId);
        node.setParentId(position.parent().getId());
        node.setName(input.getName());
        node.setCategoryCode(input.getCategoryCode());
        node.setCategoryName(input.getCategoryName());
        node.setSortNo(position.sortNo());
        node.setInnerCode(buildInnerCode(position.parent().getInnerCode(), position.sortNo()));
        projectCbsDao.insert(node);
        rebuildChildren(position.parent());
        return node.getId();
    }

    /**
     * 修改项目 CBS 节点名称与分类。
     *
     * <p>改名只改节点的显示名称，不改写标准节点的原始名称快照（source_detail_name），
     * 以便后续与平台模板比对时仍能看到原始结构名。</p>
     */
    public void updateNode(String projectId, String nodeId, ProjectCbsNodeInput input) {
        ProjectCbs node = requireNode(projectId, nodeId);
        node.setName(input.getName());
        if (StringUtils.hasText(input.getCategoryCode())) {
            node.setCategoryCode(input.getCategoryCode());
        }
        if (StringUtils.hasText(input.getCategoryName())) {
            node.setCategoryName(input.getCategoryName());
        }
        projectCbsDao.updateById(node);
    }

    /**
     * 删除项目 CBS 节点及其全部下级。
     *
     * <p>节点下已挂接料表工程量项时拒绝删除，避免出现悬空引用。删除后重算同级顺序。</p>
     */
    public void deleteNode(String projectId, String nodeId) {
        ProjectCbs node = requireNode(projectId, nodeId);
        if (node.getParentId() == null) {
            throw new BusinessException("项目根节点不可删除");
        }
        List<String> ids = new ArrayList<>();
        ids.add(node.getId());
        collectChildIds(projectId, node.getId(), ids);
        if (fileItemDao.selectCount(new QueryWrapper<FileItem>()
                .in("project_cbs_id", ids)) > 0) {
            throw new BusinessException("该结构下已挂接工程量项，请先解除挂接");
        }
        ProjectCbs parent = requireNode(projectId, node.getParentId());
        // 同步清理这些节点的定额库挂载记录，避免留下悬空引用。
        projectCbsDeLibraryDao.delete(new QueryWrapper<ProjectCbsDeLibrary>()
                .eq("project_id", projectId)
                .in("project_cbs_id", ids));
        projectCbsDao.deleteByIds(ids);
        rebuildChildren(parent);
    }

    /**
     * 复制项目 CBS 节点及其全部下级，副本插入到原节点的同级位置。
     *
     * <p>副本重新生成 UUID、父子关系、排序号与层级码，与原节点互不影响。</p>
     *
     * @return 副本根节点的 UUID
     */
    public String copyNode(String projectId, String nodeId) {
        ProjectCbs source = requireNode(projectId, nodeId);
        if (source.getParentId() == null) {
            throw new BusinessException("项目根节点不可复制");
        }
        ProjectCbs parent = requireNode(projectId, source.getParentId());
        int sortNo = nextSortNo(projectId, parent.getId());
        reserveSortNos(projectId, parent, sortNo, 1);
        ProjectCbs copy = copyNodeRecord(source, projectId, parent, sortNo);
        copyChildren(source, projectId, copy);
        rebuildChildren(parent);
        return copy.getId();
    }

    /**
     * 移动项目 CBS 节点：调整同级顺序或调整父子关系。
     *
     * <p>支持四个方向：上移、下移、升级、降级。禁止把节点移动到自身或自身子孙之下。
     * 移动完成后递归重算受影响子树的 sort_no 与 inner_code。</p>
     */
    public ProjectCbsOperationResult moveNode(String projectId, String nodeId, ProjectCbsMoveInput input) {
        ProjectCbs node = requireNode(projectId, nodeId);
        if (node.getParentId() == null) {
            throw new BusinessException("项目根节点不可移动");
        }
        ProjectCbs parent = requireNode(projectId, node.getParentId());
        String direction = input.getDirection() == null ? "" : input.getDirection().trim().toUpperCase();
        // 重算起点：升级时新父节点是旧父节点的祖先，需从更高一层重算才能覆盖新位置。
        ProjectCbs rebuildFrom = parent;
        List<String> affected = new ArrayList<>();
        switch (direction) {
            case DIRECTION_UP -> {
                moveWithinSiblings(projectId, node, parent, -1);
                affected.add(node.getId());
            }
            case DIRECTION_DOWN -> {
                moveWithinSiblings(projectId, node, parent, 1);
                affected.add(node.getId());
            }
            case DIRECTION_PROMOTE -> {
                rebuildFrom = promoteNode(projectId, node, parent);
                affected.add(node.getId());
            }
            case DIRECTION_DEMOTE -> {
                demoteNode(projectId, node, parent);
                affected.add(node.getId());
            }
            default -> throw new BusinessException("不支持的移动方向：" + input.getDirection());
        }
        rebuildChildren(rebuildFrom);
        ProjectCbsOperationResult result = new ProjectCbsOperationResult();
        result.setProjectId(projectId);
        result.setNodeIds(affected);
        result.setMessage("移动成功");
        return result;
    }

    /** 在同级中上移或下移一位，并按新顺序重写排序号。 */
    private void moveWithinSiblings(String projectId, ProjectCbs node, ProjectCbs parent, int offset) {
        List<ProjectCbs> siblings = listChildren(projectId, parent.getId());
        int index = indexOf(siblings, node.getId());
        int target = index + offset;
        if (target < 0 || target >= siblings.size()) {
            throw new BusinessException(offset < 0 ? "该节点已是第一个同级节点" : "该节点已是最后一个同级节点");
        }
        ProjectCbs moved = siblings.remove(index);
        siblings.add(target, moved);
        applySortNos(siblings);
    }

    /** 升级：节点变为其父节点的同级节点，挂到父节点的父节点下、紧跟父节点之后。 */
    private ProjectCbs promoteNode(String projectId, ProjectCbs node, ProjectCbs parent) {
        if (parent.getParentId() == null) {
            throw new BusinessException("该节点已在顶级，无法继续升级");
        }
        ProjectCbs grandParent = requireNode(projectId, parent.getParentId());
        assertNotSelfOrDescendant(projectId, node.getId(), grandParent.getId());
        List<ProjectCbs> uncles = listChildren(projectId, grandParent.getId());
        int parentIndex = indexOf(uncles, parent.getId());
        if (parentIndex < 0) {
            throw new BusinessException("父节点状态异常，请刷新后重试");
        }
        uncles.add(parentIndex + 1, node);
        node.setParentId(grandParent.getId());
        applySortNos(uncles);
        projectCbsDao.updateById(node);
        return grandParent;
    }

    /**
     * 降级：节点变为其前一个兄弟节点的子节点，挂在该兄弟的末尾。
     *
     * <p>前一个兄弟节点为“单位工程”时拒绝降级：单位工程是最末级分类，下面不允许再挂子节点。</p>
     */
    private void demoteNode(String projectId, ProjectCbs node, ProjectCbs parent) {
        List<ProjectCbs> siblings = listChildren(projectId, parent.getId());
        int index = indexOf(siblings, node.getId());
        if (index <= 0) {
            throw new BusinessException("没有可降级的上级节点");
        }
        ProjectCbs newParent = siblings.get(index - 1);
        if (LOWEST_CATEGORY_NAME.equals(newParent.getCategoryName())) {
            throw new BusinessException("上一级节点“" + newParent.getName() + "”为单位工程，不允许降级挂载到单位工程下");
        }
        assertNotSelfOrDescendant(projectId, node.getId(), newParent.getId());
        int sortNo = nextSortNo(projectId, newParent.getId());
        node.setParentId(newParent.getId());
        node.setSortNo(sortNo);
        node.setInnerCode(buildInnerCode(newParent.getInnerCode(), sortNo));
        projectCbsDao.updateById(node);
    }

    /** 校验目标父节点不是节点自身，也不是节点的后代。 */
    private void assertNotSelfOrDescendant(String projectId, String nodeId, String targetParentId) {
        if (Objects.equals(nodeId, targetParentId)) {
            throw new BusinessException("不能移动到自身之下");
        }
        List<String> ids = new ArrayList<>();
        collectChildIds(projectId, nodeId, ids);
        if (ids.contains(targetParentId)) {
            throw new BusinessException("不能移动到自身或子孙节点之下");
        }
    }

    /** 校验节点存在且属于当前项目。 */
    private ProjectCbs requireNode(String projectId, String nodeId) {
        ProjectCbs node = projectCbsDao.selectById(nodeId);
        if (node == null || !projectId.equals(node.getProjectId())) {
            throw new BusinessException("节点不存在");
        }
        return node;
    }

    /** 查询指定父节点下的直接下级。 */
    private List<ProjectCbs> listChildren(String projectId, String parentId) {
        if (!StringUtils.hasText(parentId)) {
            return List.of();
        }
        return projectCbsDao.selectList(new QueryWrapper<ProjectCbs>()
                .eq("project_id", projectId)
                .eq("parent_id", parentId)
                .orderByAsc("sort_no")
                .orderByAsc("id"));
    }

    /** 在节点集合中查找指定节点，返回其下标，找不到时返回 -1。 */
    private int indexOf(List<ProjectCbs> nodes, String nodeId) {
        for (int i = 0; i < nodes.size(); i++) {
            if (nodes.get(i).getId().equals(nodeId)) {
                return i;
            }
        }
        return -1;
    }

    /** 递归收集全部下级节点 ID。 */
    private void collectChildIds(String projectId, String parentId, List<String> ids) {
        for (ProjectCbs child : listChildren(projectId, parentId)) {
            ids.add(child.getId());
            collectChildIds(projectId, child.getId(), ids);
        }
    }

    /**
     * 确保项目 CBS 根节点存在，不存在时按项目名称创建。
     *
     * @return 项目 CBS 根节点
     */
    public ProjectCbs ensureCbsRoot(String projectId) {
        ProjectCbs root = findCbsRoot(projectId);
        if (root != null) {
            return root;
        }
        Project project = projectDao.selectById(projectId);
        if (project == null) {
            throw new BusinessException("项目不存在");
        }
        root = new ProjectCbs();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        root.setProjectId(projectId);
        root.setParentId(null);
        // 根节点名称取项目名称，层级路径码固定为首层。
        root.setName(project.getName());
        root.setSortNo(1);
        root.setInnerCode(CBS_ROOT_INNER_CODE);
        try {
            projectCbsDao.insert(root);
        } catch (DuplicateKeyException ex) {
            // 并发创建时唯一索引 uq_sc_project_cbs_root 会拦截，改为复用已存在的根节点。
            ProjectCbs existing = findCbsRoot(projectId);
            if (existing == null) {
                throw ex;
            }
            return existing;
        }
        return root;
    }

    /** 查询项目的 CBS 根节点，不存在时返回空。 */
    private ProjectCbs findCbsRoot(String projectId) {
        return projectCbsDao.selectOne(new QueryWrapper<ProjectCbs>()
                .eq("project_id", projectId)
                .isNull("parent_id")
                .orderByAsc("sort_no")
                .last("LIMIT 1"));
    }

    /**
     * 推导挂接位置。
     *
     * <p>规则：未选中右侧节点时挂到项目根节点；选中非叶子节点时挂到该节点下面；
     * 选中叶子节点时挂到该叶子节点的父节点下作为同级节点（紧随该叶子之后）。</p>
     */
    private TargetPosition resolveTargetPosition(String projectId, String targetNodeId) {
        if (!StringUtils.hasText(targetNodeId)) {
            ProjectCbs root = ensureCbsRoot(projectId);
            return new TargetPosition(root, nextSortNo(projectId, root.getId()));
        }
        ProjectCbs target = requireNode(projectId, targetNodeId);
        if (target.getParentId() == null) {
            // 选中的是项目根节点：挂在它下面。
            return new TargetPosition(target, nextSortNo(projectId, target.getId()));
        }
        if (hasChildren(projectId, target.getId())) {
            // 选中非叶子节点：挂到该节点下面。
            return new TargetPosition(target, nextSortNo(projectId, target.getId()));
        }
        // 选中叶子节点：挂到其父节点下，作为该叶子的同级节点。
        ProjectCbs parent = requireNode(projectId, target.getParentId());
        int after = target.getSortNo() == null ? 0 : target.getSortNo();
        return new TargetPosition(parent, after + 1);
    }

    /** 判断节点是否存在下级。 */
    private boolean hasChildren(String projectId, String nodeId) {
        return projectCbsDao.selectCount(new QueryWrapper<ProjectCbs>()
                .eq("project_id", projectId)
                .eq("parent_id", nodeId)) > 0;
    }

    /**
     * 为 count 个待写入节点腾出排序号：同级中排序号大于等于 fromSortNo 的节点整体后移。
     */
    private void reserveSortNos(String projectId, ProjectCbs parent, int fromSortNo, int count) {
        if (count <= 0) {
            return;
        }
        for (ProjectCbs sibling : listChildren(projectId, parent.getId())) {
            if (sibling.getSortNo() != null && sibling.getSortNo() >= fromSortNo) {
                sibling.setSortNo(sibling.getSortNo() + count);
                projectCbsDao.updateById(sibling);
            }
        }
    }

    /**
     * 递归重算父节点下全部子树的排序号与层级路径码。
     *
     * <p>子节点按当前顺序重新编号为 1..n，并据此重算 inner_code，
     * 保证排序与层级路径始终自洽。</p>
     */
    private void rebuildChildren(ProjectCbs parent) {
        List<ProjectCbs> children = listChildren(parent.getProjectId(), parent.getId());
        int sortNo = 1;
        for (ProjectCbs child : children) {
            String innerCode = buildInnerCode(parent.getInnerCode(), sortNo);
            if (!Objects.equals(child.getSortNo(), sortNo)
                    || !Objects.equals(child.getInnerCode(), innerCode)) {
                child.setSortNo(sortNo);
                child.setInnerCode(innerCode);
                projectCbsDao.updateById(child);
            }
            rebuildChildren(child);
            sortNo++;
        }
    }

    /** 按给定顺序重写排序号。 */
    private void applySortNos(List<ProjectCbs> nodes) {
        int sortNo = 1;
        for (ProjectCbs node : nodes) {
            if (!Objects.equals(node.getSortNo(), sortNo)) {
                node.setSortNo(sortNo);
                projectCbsDao.updateById(node);
            }
            sortNo++;
        }
    }

    /**
     * 按勾选集合裁剪标准结构：未勾选的节点被跳过，其下已勾选分支提升为上一级。
     */
    private List<CbsDetailNode> prune(List<CbsDetailNode> nodes, Set<String> selected) {
        List<CbsDetailNode> result = new ArrayList<>();
        for (CbsDetailNode node : nodes) {
            List<CbsDetailNode> children = prune(node.getChildren(), selected);
            if (selected.contains(node.getId())) {
                CbsDetailNode copy = new CbsDetailNode();
                copy.setId(node.getId());
                copy.setCbsId(node.getCbsId());
                copy.setParentId(node.getParentId());
                copy.setCode(node.getCode());
                copy.setName(node.getName());
                copy.setCategoryCode(node.getCategoryCode());
                copy.setCategoryName(node.getCategoryName());
                copy.setSortNo(node.getSortNo());
                copy.setInnerCode(node.getInnerCode());
                copy.setChildren(children);
                result.add(copy);
            } else {
                result.addAll(children);
            }
        }
        return result;
    }

    /**
     * 建立平台模板树的索引：节点、父节点、子节点与顶级节点集合。
     */
    private TemplateIndex indexTemplate(List<CbsDetailNode> roots) {
        Map<String, CbsDetailNode> nodeById = new LinkedHashMap<>();
        Map<String, String> parentById = new HashMap<>();
        Map<String, List<String>> childIdsById = new HashMap<>();
        Set<String> topLevelIds = new HashSet<>();
        for (CbsDetailNode root : roots) {
            topLevelIds.add(root.getId());
            indexTemplateNode(root, null, nodeById, parentById, childIdsById);
        }
        return new TemplateIndex(nodeById, parentById, childIdsById, topLevelIds);
    }

    /** 递归登记模板树节点。 */
    private void indexTemplateNode(CbsDetailNode node, String parentId,
            Map<String, CbsDetailNode> nodeById, Map<String, String> parentById,
            Map<String, List<String>> childIdsById) {
        nodeById.put(node.getId(), node);
        parentById.put(node.getId(), parentId);
        childIdsById.put(node.getId(), new ArrayList<>());
        if (parentId != null) {
            childIdsById.get(parentId).add(node.getId());
        }
        for (CbsDetailNode child : node.getChildren()) {
            indexTemplateNode(child, node.getId(), nodeById, parentById, childIdsById);
        }
    }

    /**
     * 计算最终引入的明细集合。
     *
     * <p>级联为是：自动关联所选节点的父节点（不含顶级容器）与全部子节点。
     * 级联为否：只引入明确勾选的节点。</p>
     *
     * <p>顶级节点是全选开关，勾选它等同于勾选其下全部分支，因此两种级联方式下都取其整棵子树。</p>
     *
     * <p>明确取消的节点及其子树从最终集合中排除，避免被级联重新带出；
     * 但被明确勾选的节点始终保留。</p>
     */
    private Set<String> resolveFinalIds(List<String> checkedIds, List<String> excludedIds,
            boolean cascade, TemplateIndex index) {
        Set<String> checked = new HashSet<>(checkedIds);
        Set<String> finalIds = new HashSet<>(checkedIds);
        for (String checkedId : checkedIds) {
            if (index.topLevelIds().contains(checkedId)) {
                // 顶级节点是全选开关，取其下全部分支。
                collectSubtreeIds(checkedId, index, finalIds);
                continue;
            }
            if (!cascade) {
                continue;
            }
            // 向下关联全部子节点。
            collectSubtreeIds(checkedId, index, finalIds);
            // 向上关联父节点，顶级容器只作容器不进入项目层级。
            String parentId = index.parentById().get(checkedId);
            while (parentId != null && !index.topLevelIds().contains(parentId)) {
                finalIds.add(parentId);
                parentId = index.parentById().get(parentId);
            }
        }
        if (excludedIds == null || excludedIds.isEmpty()) {
            return finalIds;
        }
        // 明确取消的节点及其子树从最终集合中排除。
        Set<String> excluded = new HashSet<>();
        for (String excludedId : excludedIds) {
            if (!index.nodeById().containsKey(excludedId)) {
                continue;
            }
            collectSubtreeIds(excludedId, index, excluded);
        }
        for (String excludedId : excluded) {
            if (!checked.contains(excludedId)) {
                finalIds.remove(excludedId);
            }
        }
        return finalIds;
    }

    /** 递归收集节点自身及其全部后代 ID。 */
    private void collectSubtreeIds(String nodeId, TemplateIndex index, Set<String> collector) {
        collector.add(nodeId);
        for (String childId : index.childIdsById().getOrDefault(nodeId, List.of())) {
            collectSubtreeIds(childId, index, collector);
        }
    }

    /**
     * 写入单个标准节点，并返回落库后的记录。
     *
     * <p>每次引入都生成全新的 UUID，不与项目中已有的同名节点合并，
     * 保证多次引入的结果彼此独立。</p>
     */
    private ProjectCbs insertNode(CbsDetailNode source, String projectId, ProjectCbs parent,
            CbsTemplateView template, int sortNo) {
        ProjectCbs node = new ProjectCbs();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        node.setProjectId(projectId);
        node.setParentId(parent.getId());
        node.setCode(source.getCode());
        node.setName(source.getName());
        // 保留标准节点的原始名称快照，便于后续与平台模板比对。
        node.setSourceDetailName(source.getName());
        node.setCategoryCode(source.getCategoryCode());
        node.setCategoryName(source.getCategoryName());
        node.setSortNo(sortNo);
        node.setInnerCode(buildInnerCode(parent.getInnerCode(), sortNo));
        node.setSourceCbsId(template.getId());
        node.setSourceCbsDetailId(source.getId());
        node.setSourceVersionNo(template.getVersionNo());
        projectCbsDao.insert(node);
        return node;
    }

    /**
     * 递归写入下级节点。
     *
     * @return 本次写入的下级节点总数
     */
    private int insertChildren(CbsDetailNode parentSource, String projectId, ProjectCbs parent,
            CbsTemplateView template) {
        int count = 0;
        int sortNo = 1;
        for (CbsDetailNode child : parentSource.getChildren()) {
            ProjectCbs created = insertNode(child, projectId, parent, template, sortNo++);
            count++;
            count += insertChildren(child, projectId, created, template);
        }
        return count;
    }

    /** 递归复制下级节点。 */
    private void copyChildren(ProjectCbs source, String projectId, ProjectCbs target) {
        int sortNo = 1;
        for (ProjectCbs child : listChildren(projectId, source.getId())) {
            ProjectCbs copy = copyNodeRecord(child, projectId, target, sortNo++);
            copyChildren(child, projectId, copy);
        }
    }

    /** 生成一条节点副本记录。 */
    private ProjectCbs copyNodeRecord(ProjectCbs source, String projectId, ProjectCbs parent, int sortNo) {
        ProjectCbs copy = new ProjectCbs();
        // id、创建人、所属机构、创建时间由 UuidIdMetaObjectHandler 在插入时自动填充
        copy.setProjectId(projectId);
        copy.setParentId(parent.getId());
        copy.setCode(source.getCode());
        copy.setName(source.getName());
        copy.setSourceDetailName(source.getSourceDetailName());
        copy.setCategoryCode(source.getCategoryCode());
        copy.setCategoryName(source.getCategoryName());
        copy.setSortNo(sortNo);
        copy.setInnerCode(buildInnerCode(parent.getInnerCode(), sortNo));
        copy.setSourceCbsId(source.getSourceCbsId());
        copy.setSourceCbsDetailId(source.getSourceCbsDetailId());
        copy.setSourceVersionNo(source.getSourceVersionNo());
        projectCbsDao.insert(copy);
        return copy;
    }

    /** 拼接层级路径码：父路径 + 分隔符 + 同级序号。 */
    private String buildInnerCode(String parentInnerCode, int sortNo) {
        if (!StringUtils.hasText(parentInnerCode)) {
            return String.valueOf(sortNo);
        }
        return parentInnerCode + INNER_CODE_SEPARATOR + sortNo;
    }

    /** 计算父节点下可用的下一个同级排序号。 */
    private int nextSortNo(String projectId, String parentId) {
        ProjectCbs latest = projectCbsDao.selectOne(new QueryWrapper<ProjectCbs>()
                .eq("project_id", projectId)
                .eq("parent_id", parentId)
                .orderByDesc("sort_no")
                .last("LIMIT 1"));
        return latest == null || latest.getSortNo() == null ? 1 : latest.getSortNo() + 1;
    }

    /** 按 parent_id 组装项目 CBS 树。 */
    private List<ProjectCbsNodeView> buildTree(List<ProjectCbs> nodes) {
        List<ProjectCbsNodeView> views = nodes.stream().map(this::toView).toList();
        List<ProjectCbsNodeView> roots = new ArrayList<>();
        for (ProjectCbsNodeView view : views) {
            ProjectCbsNodeView parent = findParent(views, view.getParentId());
            if (parent == null) {
                roots.add(view);
            } else {
                parent.getChildren().add(view);
            }
        }
        return roots;
    }

    /** 在节点集合中查找指定父节点，父节点为空表示顶级节点。 */
    private ProjectCbsNodeView findParent(List<ProjectCbsNodeView> views, String parentId) {
        if (!StringUtils.hasText(parentId)) {
            return null;
        }
        for (ProjectCbsNodeView view : views) {
            if (view.getId().equals(parentId)) {
                return view;
            }
        }
        return null;
    }

    /** 实体转视图。 */
    private ProjectCbsNodeView toView(ProjectCbs entity) {
        ProjectCbsNodeView view = new ProjectCbsNodeView();
        view.setId(entity.getId());
        view.setProjectId(entity.getProjectId());
        view.setParentId(entity.getParentId());
        view.setCode(entity.getCode());
        view.setName(entity.getName());
        view.setCategoryCode(entity.getCategoryCode());
        view.setCategoryName(entity.getCategoryName());
        view.setSortNo(entity.getSortNo());
        view.setInnerCode(entity.getInnerCode());
        view.setSourceCbsId(entity.getSourceCbsId());
        view.setSourceCbsDetailId(entity.getSourceCbsDetailId());
        return view;
    }

    /** 挂接位置：目标父节点与在目标父节点下的排序号。 */
    private record TargetPosition(ProjectCbs parent, int sortNo) {
    }

    /** 平台模板树索引。 */
    private record TemplateIndex(Map<String, CbsDetailNode> nodeById,
            Map<String, String> parentById,
            Map<String, List<String>> childIdsById,
            Set<String> topLevelIds) {
    }
}
