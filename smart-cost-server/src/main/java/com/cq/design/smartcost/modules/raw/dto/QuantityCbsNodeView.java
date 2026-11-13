package com.cq.design.smartcost.modules.raw.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/** 工程量编制页左侧 CBS 树节点：项目 CBS 节点附加挂接工程量统计。 */
@Data
public class QuantityCbsNodeView {
    /** 节点 UUID。 */
    private String id;
    /** 父节点 UUID，项目根节点为空。 */
    private String parentId;
    /** 项目 CBS 编码。 */
    private String code;
    /** 节点名称。 */
    private String name;
    /** 分类字典编码。 */
    private String categoryCode;
    /** 分类名称快照。 */
    private String categoryName;
    /** 同级排序号。 */
    private Integer sortNo;
    /** 层级路径码。 */
    private String innerCode;
    /** 挂接到该节点的工程量结构项数量。 */
    private int itemCount;
    /** 下级节点。 */
    private List<QuantityCbsNodeView> children = new ArrayList<>();

    /** 是否最底层节点（无下级 CBS）。 */
    public boolean isBottomLevel() {
        return children.isEmpty();
    }
}
