package com.cq.design.smartcost.modules.raw.service;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 料表解析共享模型与表头语义规则：PDF 与 Word 解析器共用的数据结构与标签匹配规则，
 * 保证两种来源解析出的树表结构（表头 + 原始行）完全一致。
 */
public final class MaterialTableModels {

    /** 列语义：覆盖三类料表（设备表/材料表/名称规格表）的全部表头标签。 */
    public enum Semantic {
        SERIAL, EQUIPMENT_TAG, DESCRIPTION, NOMINAL_SIZE, UNIT,
        QUANTITY, UNIT_WEIGHT, TOTAL_WEIGHT, REMARK
    }

    /**
     * 表头标签前缀 → 语义映射，按声明顺序匹配（先特殊后一般）。
     * "单位"与"单台/单件质量"前两字不同，"数量"与"单"字头标签不冲突，天然区分。
     */
    public static final String[][] LABEL_RULES = {
            {"单件质量", "UNIT_WEIGHT"}, {"单台质量", "UNIT_WEIGHT"},
            {"总质量", "TOTAL_WEIGHT"},
            {"设备位号", "EQUIPMENT_TAG"},
            {"公称尺寸", "NOMINAL_SIZE"},
            {"名称", "DESCRIPTION"}, {"描述", "DESCRIPTION"},
            {"备注", "REMARK"},
            {"序号", "SERIAL"},
            {"单位", "UNIT"},
            {"数量", "QUANTITY"}
    };

    /** 封面表类型标题匹配（允许字间空格，Word 封面常写作"材 料 表"）。 */
    public static final Pattern TABLE_TYPE_PATTERN =
            Pattern.compile("(主要材料表|主要设备表|材料表|设备表|主材表)");

    private MaterialTableModels() { }

    /** 按前缀规则匹配表头标签语义；未识别的表头文字返回 null。 */
    public static Semantic matchSemantic(String text) {
        if (text == null || text.isEmpty()) {
            return null;
        }
        for (String[] rule : LABEL_RULES) {
            if (text.startsWith(rule[0])) {
                return Semantic.valueOf(rule[1]);
            }
        }
        return null;
    }

    /** 表头解析结果：表类型、表专业、工程名称（表名称标题区）。 */
    public static final class ParsedHeader {
        public String tableType;
        public String specialty;
        public String projectSection;
    }

    /** 数据行解析结果：各列原始文本，未出现在该料表格式的列为 null（入库前统一为空串处理）。 */
    public static final class ParsedRow {
        public String serialNo;
        public String equipmentTag;
        public String description;
        public String nominalSize;
        public String unit;
        public String quantity;
        public String unitWeight;
        public String totalWeight;
        public String remark;
    }

    /** 整个文件的解析结果。 */
    public static final class ParsedTable {
        public final ParsedHeader header = new ParsedHeader();
        public final List<ParsedRow> rows = new ArrayList<>();
    }
}
