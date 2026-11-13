package com.cq.design.smartcost.modules.matching.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.cq.design.smartcost.common.constants.Constants;
import com.cq.design.smartcost.common.service.BusinessService;
import com.cq.design.smartcost.common.web.BusinessException;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import com.cq.design.smartcost.modules.file.service.FileService;
import com.cq.design.smartcost.modules.matching.dao.FileItemMatchConsumeDao;
import com.cq.design.smartcost.modules.matching.dao.FileItemMatchDao;
import com.cq.design.smartcost.modules.matching.dao.FileItemMatchRelationDao;
import com.cq.design.smartcost.modules.matching.dto.QuotaCellUpdateInput;
import com.cq.design.smartcost.modules.matching.dto.QuotaManualMatchInput;
import com.cq.design.smartcost.modules.matching.dto.QuotaMatchConsumeView;
import com.cq.design.smartcost.modules.matching.dto.QuotaMatchView;
import com.cq.design.smartcost.modules.matching.model.FileItemMatch;
import com.cq.design.smartcost.modules.matching.model.FileItemMatchConsume;
import com.cq.design.smartcost.modules.matching.model.FileItemMatchRelation;
import com.cq.design.smartcost.modules.quota.dao.DeItemDao;
import com.cq.design.smartcost.modules.quota.model.DeItem;
import com.cq.design.smartcost.modules.raw.dao.FileItemDao;
import com.cq.design.smartcost.modules.raw.model.FileItem;
import com.cq.design.smartcost.modules.rule.dto.RuleA06ItemView;
import com.cq.design.smartcost.modules.rule.service.RuleA06Service;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.*;

/**
 * 定额/指标匹配业务服务：按批次 + CBS 最底层节点查询定额匹配结果
 * （sc_file_item_match 为根节点，sc_file_item_match_consume 为子节点人材机消耗），
 * 并支持右侧表格「单位/工程量计算式/工程量」三个可编辑字段的落库。
 */
@Service
public class QuotaMatchService extends BusinessService {

    @Resource(name = "fileService")
    private FileService fileService;
    @Resource(name = "fileItemDao")
    private FileItemDao fileItemDao;
    @Resource(name = "fileItemMatchDao")
    private FileItemMatchDao fileItemMatchDao;
    @Resource(name = "fileItemMatchConsumeDao")
    private FileItemMatchConsumeDao fileItemMatchConsumeDao;
    @Resource(name = "fileItemMatchRelationDao")
    private FileItemMatchRelationDao fileItemMatchRelationDao;
    @Resource(name = "deItemDao")
    private DeItemDao deItemDao;
    @Resource(name = "ruleA06Service")
    private RuleA06Service ruleA06Service;

    /**
     * 指定批次下挂到某 CBS 最底层节点的定额匹配树（线性查询后组装两层：
     * 根节点 = sc_file_item_match，子节点 = sc_file_item_match_consume）。
     */
    public List<QuotaMatchView> items(String cbsId, String batchId) {
        List<FileInfo> files = fileService.list(Constants.FileSource.BATCH, batchId);
        if (files == null || files.isEmpty()) {
            return List.of();
        }
        List<FileItem> items = fileItemDao.selectList(new QueryWrapper<FileItem>()
                .in("file_id", files.stream().map(FileInfo::getId).toList())
                .eq("project_cbs_id", cbsId));
        if (items.isEmpty()) {
            return List.of();
        }
        List<FileItemMatch> matches = fileItemMatchDao.selectList(new QueryWrapper<FileItemMatch>()
                .in("file_item_id", items.stream().map(FileItem::getId).toList())
                .orderByAsc("create_date")
                .orderByAsc("id"));
        if (matches.isEmpty()) {
            return List.of();
        }
        List<String> matchIds = matches.stream().map(FileItemMatch::getId).toList();
        // 工程量结构项类型（1302 主材 / 1303 设备）随根节点返回，供前端判断「升级」可用性。
        Map<String, String> itemTypesById = new HashMap<>();
        for (FileItem item : items) {
            itemTypesById.put(item.getId(), item.getType());
        }
        Map<String, List<FileItemMatchConsume>> consumesByMatch = new HashMap<>();
        for (FileItemMatchConsume consume : fileItemMatchConsumeDao.selectList(new QueryWrapper<FileItemMatchConsume>()
                .in("match_id", matchIds)
                .orderByAsc("sort_no"))) {
            consumesByMatch.computeIfAbsent(consume.getMatchId(), key -> new ArrayList<>()).add(consume);
        }

        List<QuotaMatchView> result = new ArrayList<>();
        for (FileItemMatch match : matches) {
            QuotaMatchView view = new QuotaMatchView();
            view.setId(match.getId());
            view.setFileItemId(match.getFileItemId());
            view.setItemType(itemTypesById.get(match.getFileItemId()));
            view.setIsMain(match.getIsMain());
            view.setCode(match.getCode());
            view.setName(match.getName());
            view.setUnit(match.getUnit());
            view.setFormula(match.getFormula());
            view.setQuantity(toPlainString(match.getQuantity()));
            view.setPrice(toPlainString(match.getBasePrice()));
            view.setMatchStatus(match.getMatchStatus());
            view.setMatchMethod(match.getMatchMethod());
            for (FileItemMatchConsume consume : consumesByMatch.getOrDefault(match.getId(), List.of())) {
                QuotaMatchConsumeView consumeView = new QuotaMatchConsumeView();
                consumeView.setId(consume.getId());
                consumeView.setMatchId(consume.getMatchId());
                consumeView.setCode(consume.getCode());
                consumeView.setName(consume.getName());
                consumeView.setType(consume.getType());
                consumeView.setUnit(consume.getUnit());
                consumeView.setFormula(consume.getFormula());
                consumeView.setQuantity(toPlainString(consume.getQuantity()));
                consumeView.setPrice(toPlainString(consume.getPrice()));
                consumeView.setSortNo(consume.getSortNo());
                view.getChildren().add(consumeView);
            }
            result.add(view);
        }
        return result;
    }

    /** 更新定额根节点（sc_file_item_match）的可编辑字段：单位、工程量计算式、工程量。 */
    public void updateMatch(QuotaCellUpdateInput input) {
        FileItemMatch match = requireMatch(input);
        fileItemMatchDao.update(null, new UpdateWrapper<FileItemMatch>()
                .eq("id", match.getId())
                .set("unit", input.getUnit())
                .set("formula", input.getFormula())
                .set("quantity", input.getQuantity()));
        // 主定额工程量变化时，按关联规则的计算式联动刷新关联定额工程量。
        if (input.getQuantity() != null) {
            propagateQuantityToAssociated(match, input.getQuantity());
        }
    }

    /**
     * 主定额工程量联动：主定额工作量 × 换算系数（sc_rule_a06_de_item 中
     * 关联工作量 / 原始工作量，缺省 1）= 关联定额工作量。换算无法解析时跳过该条关联，不覆盖人工修改。
     */
    private void propagateQuantityToAssociated(FileItemMatch main, BigDecimal mainQuantity) {
        List<FileItemMatchRelation> relations = fileItemMatchRelationDao.selectList(
                new QueryWrapper<FileItemMatchRelation>().eq("source_match_id", main.getId()));
        if (relations.isEmpty()) {
            return;
        }
        Map<String, BigDecimal> factors = relationFactors(main);
        for (FileItemMatchRelation relation : relations) {
            FileItemMatch associated = fileItemMatchDao.selectById(relation.getAssociatedMatchId());
            if (associated == null) {
                continue;
            }
            BigDecimal factor = factors.get(associated.getDeItemId());
            if (factor == null) {
                continue;
            }
            fileItemMatchDao.update(null, new UpdateWrapper<FileItemMatch>()
                    .eq("id", associated.getId())
                    .set("quantity", mainQuantity.multiply(factor)));
        }
    }

    /**
     * 取主定额各关联定额的换算系数（key = 关联定额 sc_de_item.id）：
     * 经 A-06 规则区间展开得到关联明细，系数 = 关联工作量 / 主定额工作量。
     */
    private Map<String, BigDecimal> relationFactors(FileItemMatch main) {
        Map<String, BigDecimal> factors = new HashMap<>();
        if (main.getDeItemId() == null) {
            return factors;
        }
        for (RuleA06ItemView view : ruleA06Service.listByOrigin(main.getDeItemId())) {
            BigDecimal origin = RuleA06Service.parseQuantity(view.getOriginQuantity());
            BigDecimal related = RuleA06Service.parseQuantity(view.getRelatedQuantity());
            if (origin == null || related == null || view.getRelatedItemId() == null) {
                continue;
            }
            if (origin.compareTo(BigDecimal.ZERO) == 0) {
                continue;
            }
            factors.putIfAbsent(view.getRelatedItemId(),
                    related.divide(origin, 6, java.math.RoundingMode.HALF_UP));
        }
        return factors;
    }

    /** 更新人材机消耗子节点（sc_file_item_match_consume）的可编辑字段。 */
    public void updateConsume(QuotaCellUpdateInput input) {
        FileItemMatchConsume consume = fileItemMatchConsumeDao.selectById(requireInputId(input));
        if (consume == null) {
            throw new BusinessException("消耗记录不存在或已被重建，请刷新后重试");
        }
        fileItemMatchConsumeDao.update(null, new UpdateWrapper<FileItemMatchConsume>()
                .eq("id", consume.getId())
                .set("unit", input.getUnit())
                .set("formula", input.getFormula())
                .set("quantity", input.getQuantity()));
    }

    /**
     * 人工选择定额/指标：把匹配记录手动指定为定额知识库中的某个子目，
     * 快照其编号/名称/单位/基价，状态置为已命中、方式置为人工。
     * 可同时选择关联定额：重建主/关联匹配关系（sc_file_item_match_relation），
     * 并把该关联沉淀为 A-06 规则明细（sc_rule_a06_de_item）。
     */
    @Transactional
    public void manualMatch(QuotaManualMatchInput input) {
        if (input == null || input.getMatchId() == null || input.getMatchId().isBlank()) {
            throw new BusinessException("定额匹配记录标识不能为空");
        }
        if (input.getDeItemId() == null || input.getDeItemId().isBlank()) {
            throw new BusinessException("请选择定额/指标子目");
        }
        FileItemMatch match = fileItemMatchDao.selectById(input.getMatchId().trim());
        if (match == null) {
            throw new BusinessException("定额记录不存在或已被重建，请刷新后重试");
        }
        DeItem deItem = deItemDao.selectById(input.getDeItemId().trim());
        if (deItem == null) {
            throw new BusinessException("所选定额/指标不存在，请重新选择");
        }
        fileItemMatchDao.update(null, new UpdateWrapper<FileItemMatch>()
                .eq("id", match.getId())
                .set("de_library_id", deItem.getDeLibraryId())
                .set("de_item_id", deItem.getId())
                .set("code", deItem.getCode())
                .set("name", deItem.getName())
                .set("unit", deItem.getUnit())
                .set("base_price", deItem.getBasePrice())
                .set("match_status", Constants.MatchStatus.MATCHED)
                .set("match_method", Constants.MatchMethod.MANUAL)
                .set("match_score", null)
                .set("match_remark", "人工选择定额/指标"));
        // 重新选择主定额后旧的关联定额全部失效：先清理再按本次选择重建。
        removeAssociatedMatches(match.getId());
        if (input.getRelatedDeItemId() != null && !input.getRelatedDeItemId().isBlank()) {
            createAssociatedMatch(match, deItem, input.getRelatedDeItemId().trim(),
                    input.getOriginQuantity(), input.getRelatedQuantity());
        }
    }

    /** 删除主定额匹配下的全部关联定额匹配（含其消耗明细与主/关联关系）。 */
    private void removeAssociatedMatches(String sourceMatchId) {
        List<FileItemMatchRelation> relations = fileItemMatchRelationDao.selectList(
                new QueryWrapper<FileItemMatchRelation>().eq("source_match_id", sourceMatchId));
        if (relations.isEmpty()) {
            return;
        }
        List<String> associatedIds = relations.stream().map(FileItemMatchRelation::getAssociatedMatchId).toList();
        fileItemMatchConsumeDao.delete(new QueryWrapper<FileItemMatchConsume>()
                .in("match_id", associatedIds));
        fileItemMatchDao.deleteByIds(associatedIds);
        fileItemMatchRelationDao.delete(new QueryWrapper<FileItemMatchRelation>()
                .eq("source_match_id", sourceMatchId));
    }

    /**
     * 创建关联定额匹配：is_main=0，快照子目信息，工程量 = 主定额工作量 × 换算系数
     * （系数 = 关联定额工作量 / 原始定额工作量，缺省 1）；
     * 写入主/关联匹配关系，并把该关联沉淀为 A-06 规则明细（同组合已存在时更新工作量）。
     */
    private void createAssociatedMatch(FileItemMatch main, DeItem mainDeItem,
                                       String relatedDeItemId, String originQuantity, String relatedQuantity) {
        if (mainDeItem.getId().equals(relatedDeItemId)) {
            throw new BusinessException("关联定额不能与主定额相同");
        }
        DeItem related = deItemDao.selectById(relatedDeItemId);
        if (related == null) {
            throw new BusinessException("所选关联定额不存在，请重新选择");
        }
        BigDecimal origin = RuleA06Service.parseQuantity(originQuantity);
        BigDecimal ratio = RuleA06Service.parseQuantity(relatedQuantity);
        BigDecimal factor = BigDecimal.ONE;
        if (origin != null && ratio != null && origin.compareTo(BigDecimal.ZERO) != 0) {
            factor = ratio.divide(origin, 6, java.math.RoundingMode.HALF_UP);
        }
        BigDecimal mainQuantity = main.getQuantity() == null ? BigDecimal.ZERO : main.getQuantity();
        FileItemMatch associated = new FileItemMatch();
        associated.setId(UUID.randomUUID().toString());
        associated.setFileItemId(main.getFileItemId());
        associated.setDeLibraryId(related.getDeLibraryId());
        associated.setDeItemId(related.getId());
        associated.setIsMain(0);
        associated.setCode(related.getCode());
        associated.setName(related.getName());
        associated.setUnit(related.getUnit());
        associated.setQuantity(mainQuantity.multiply(factor));
        associated.setBasePrice(related.getBasePrice());
        associated.setMatchStatus(Constants.MatchStatus.MATCHED);
        associated.setMatchMethod(Constants.MatchMethod.MANUAL);
        associated.setMatchRemark("关联定额（主定额 " + mainDeItem.getCode() + "）");
        fileItemMatchDao.insert(associated);
        FileItemMatchRelation relation = new FileItemMatchRelation();
        relation.setId(UUID.randomUUID().toString());
        relation.setSourceMatchId(main.getId());
        relation.setAssociatedMatchId(associated.getId());
        fileItemMatchRelationDao.insert(relation);
        // 关联沉淀为 A-06 规则明细：原始定额 → 关联定额 + 双方工作量，供后续匹配与工程量联动复用。
        ruleA06Service.deposit(mainDeItem.getDeLibraryId(), mainDeItem.getId(), related.getId(),
                originQuantity, relatedQuantity, "人工匹配创建");
    }

    /**
     * 升级为独立计价项：将未匹配（或需脱离定额）的设备/主材脱离定额关联，
     * 置空 de_library_id/de_item_id、状态置为已处理（1403），并清理该匹配下的
     * 人材机消耗明细与主/关联定额关系，之后可单独计价。
     */
    @Transactional
    public void upgrade(String matchId) {
        if (matchId == null || matchId.isBlank()) {
            throw new BusinessException("定额匹配记录标识不能为空");
        }
        FileItemMatch match = fileItemMatchDao.selectById(matchId.trim());
        if (match == null) {
            throw new BusinessException("定额记录不存在或已被重建，请刷新后重试");
        }
        if (Constants.MatchStatus.PROCESSED.equals(match.getMatchStatus())) {
            throw new BusinessException("该记录已升级为独立计价项，无需重复操作");
        }
        FileItem item = match.getFileItemId() == null ? null : fileItemDao.selectById(match.getFileItemId());
        if (item == null
                || !(Constants.ItemNodeType.MAIN_MATERIAL.equals(item.getType())
                        || Constants.ItemNodeType.EQUIPMENT.equals(item.getType()))) {
            throw new BusinessException("仅设备/主材工程量项可升级为独立计价项");
        }
        // 置空定额关联（显式 set null，MP updateById 会忽略 null 字段）。
        fileItemMatchDao.update(null, new UpdateWrapper<FileItemMatch>()
                .eq("id", match.getId())
                .set("de_library_id", null)
                .set("de_item_id", null)
                .set("match_status", Constants.MatchStatus.PROCESSED)
                .set("match_method", Constants.MatchMethod.MANUAL)
                .set("match_score", null)
                .set("match_remark", "升级为独立计价项"));
        // 清理该匹配下的人材机消耗明细。
        fileItemMatchConsumeDao.delete(new QueryWrapper<FileItemMatchConsume>()
                .eq("match_id", match.getId()));
        // 清理主/关联定额关系（作为来源或被关联的记录均失效）。
        fileItemMatchRelationDao.delete(new QueryWrapper<FileItemMatchRelation>()
                .eq("source_match_id", match.getId())
                .or()
                .eq("associated_match_id", match.getId()));
    }

    /** 校验入参并返回定额匹配记录。 */
    private FileItemMatch requireMatch(QuotaCellUpdateInput input) {
        FileItemMatch match = fileItemMatchDao.selectById(requireInputId(input));
        if (match == null) {
            throw new BusinessException("定额记录不存在或已被重建，请刷新后重试");
        }
        return match;
    }

    private String requireInputId(QuotaCellUpdateInput input) {
        if (input == null || input.getId() == null || input.getId().isBlank()) {
            throw new BusinessException("记录标识不能为空");
        }
        return input.getId().trim();
    }

    private String toPlainString(BigDecimal value) {
        return value == null ? null : value.toPlainString();
    }
}
