package com.cq.design.smartcost.modules.raw.service;

import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedHeader;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedRow;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedTable;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.Semantic;
import org.apache.poi.hwpf.HWPFDocument;
import org.apache.poi.hwpf.usermodel.Range;
import org.apache.poi.hwpf.usermodel.Table;
import org.apache.poi.hwpf.usermodel.TableIterator;
import org.apache.poi.hwpf.usermodel.TableRow;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.apache.poi.xwpf.usermodel.XWPFTableCell;
import org.apache.poi.xwpf.usermodel.XWPFTableRow;
import org.springframework.stereotype.Component;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 料表 Word 解析器（设计院固定模板，兼容 .doc 与 .docx），解析规则与 PDF 版一致：
 * 封面识别表类型/表专业/工程名称，数据区还原为"一行一条记录"的原始行，
 * 层级关系由序号形态（中文数字/阿拉伯数字/无序号）供后续业务推导。
 *
 * <p>Word 模板结构：正文为一张大表，起始若干行为封面（证书号/表类型/项目号/文件号/
 * 项目名称/专业/阶段/日期/版次），随后一行单格标题（如"材 料 表"），之后是数据行。</p>
 *
 * <p>列语义识别策略：</p>
 * <ul>
 * <li>表内存在表头行（同时含 序号/单位/数量 标签）时，按表头标签匹配语义（与 PDF 相同规则）；</li>
 * <li>无表头行时，按数据行的主导列数套用设计院固定模板的默认布局（8 列设备表带设备位号列，
 *     7 列材料表为 序号/描述/单位/数量/单件质量/总质量/备注，6 列材料表带公称尺寸列）。</li>
 * </ul>
 */
@Component
public class MaterialTableWordParser {

    /** 无表头行时按列数套用的默认列语义布局（键为列数，来自设计院固定模板实测）。 */
    private static final Map<Integer, Semantic[]> DEFAULT_LAYOUTS = new HashMap<>();

    static {
        DEFAULT_LAYOUTS.put(5, new Semantic[] {
                Semantic.SERIAL, Semantic.DESCRIPTION, Semantic.UNIT,
                Semantic.QUANTITY, Semantic.REMARK});
        DEFAULT_LAYOUTS.put(6, new Semantic[] {
                Semantic.SERIAL, Semantic.DESCRIPTION, Semantic.NOMINAL_SIZE,
                Semantic.UNIT, Semantic.QUANTITY, Semantic.REMARK});
        DEFAULT_LAYOUTS.put(7, new Semantic[] {
                Semantic.SERIAL, Semantic.DESCRIPTION, Semantic.UNIT, Semantic.QUANTITY,
                Semantic.UNIT_WEIGHT, Semantic.TOTAL_WEIGHT, Semantic.REMARK});
        DEFAULT_LAYOUTS.put(8, new Semantic[] {
                Semantic.SERIAL, Semantic.EQUIPMENT_TAG, Semantic.DESCRIPTION,
                Semantic.UNIT, Semantic.QUANTITY,
                Semantic.UNIT_WEIGHT, Semantic.TOTAL_WEIGHT, Semantic.REMARK});
    }

    /** 封面"专业：xx"键值匹配（Word 封面常写作"专  业：通  信"）。 */
    private static final Pattern SPECIALTY_PATTERN = Pattern.compile("专\\s*业\\s*[：:]\\s*(.*)$");

    /** 封面工程名称单元格的排除关键字。 */
    private static final String[] COVER_EXCLUDE_KEYWORDS =
            {"证书号", "项目号", "文件号", "专业", "阶段", "日期", "页", "版"};

    /** 解析料表 Word 文档：封面 + 数据行，产出与 PDF 解析一致的树表结构。 */
    public ParsedTable parse(byte[] content, String extension) throws IOException {
        List<List<String>> grid = "docx".equalsIgnoreCase(extension)
                ? readDocx(content) : readDoc(content);
        ParsedTable result = new ParsedTable();
        if (grid.isEmpty()) {
            return result;
        }
        int headerIndex = findHeaderRowIndex(grid);
        List<Semantic> semantics;
        List<List<String>> dataRows = new ArrayList<>();
        int firstDataIndex;
        if (headerIndex >= 0) {
            List<String> headerRow = grid.get(headerIndex);
            semantics = semanticsFromHeader(headerRow);
            if (semantics == null) {
                // 表头标签无法识别时退回固定模板布局，避免整份文件解析失败。
                semantics = defaultLayout(headerRow.size());
            }
            firstDataIndex = headerIndex + 1;
            for (int i = firstDataIndex; i < grid.size(); i++) {
                if (isDataRow(grid.get(i), semantics)) {
                    dataRows.add(grid.get(i));
                }
            }
        } else {
            int dominant = dominantColumnCount(grid);
            semantics = defaultLayout(dominant);
            firstDataIndex = -1;
            for (int i = 0; i < grid.size(); i++) {
                if (isDataRow(grid.get(i), semantics)) {
                    if (firstDataIndex < 0) {
                        firstDataIndex = i;
                    }
                    dataRows.add(grid.get(i));
                }
            }
        }
        extractCover(result.header, grid, firstDataIndex);
        if (semantics == null) {
            return result;
        }
        for (List<String> cells : dataRows) {
            ParsedRow row = toParsedRow(cells, semantics);
            if (row != null) {
                result.rows.add(row);
            }
        }
        return result;
    }

    /** 读取二进制 .doc：遍历全部表格，每个单元格规整为一个文本。 */
    private List<List<String>> readDoc(byte[] content) throws IOException {
        List<List<String>> grid = new ArrayList<>();
        try (HWPFDocument document = new HWPFDocument(new ByteArrayInputStream(content))) {
            Range range = document.getRange();
            TableIterator tables = new TableIterator(range);
            while (tables.hasNext()) {
                Table table = tables.next();
                for (int r = 0; r < table.numRows(); r++) {
                    TableRow row = table.getRow(r);
                    if (row.numCells() <= 0) {
                        // HWPF 偶发无法还原单元格的行（合并单元格区域），按空行跳过。
                        continue;
                    }
                    List<String> cells = new ArrayList<>();
                    for (int c = 0; c < row.numCells(); c++) {
                        cells.add(normalize(row.getCell(c).text()));
                    }
                    grid.add(cells);
                }
            }
        }
        return grid;
    }

    /** 读取 OOXML .docx：遍历全部表格，与 .doc 输出统一为文本行列结构。 */
    private List<List<String>> readDocx(byte[] content) throws IOException {
        List<List<String>> grid = new ArrayList<>();
        try (XWPFDocument document = new XWPFDocument(new ByteArrayInputStream(content))) {
            for (XWPFTable table : document.getTables()) {
                for (XWPFTableRow row : table.getRows()) {
                    List<String> cells = new ArrayList<>();
                    for (XWPFTableCell cell : row.getTableCells()) {
                        cells.add(normalize(cell.getText()));
                    }
                    if (!cells.isEmpty()) {
                        grid.add(cells);
                    }
                }
            }
        }
        return grid;
    }

    /** 单元格文本规整：去除单元格标记/换行/制表符，压缩连续空白为单个空格并去首尾。 */
    private String normalize(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replace("\u0007", " ").replace('\r', ' ').replace('\n', ' ')
                .replace('\t', ' ').replace('\u3000', ' ')
                .replaceAll("\\s+", " ").trim();
    }

    /** 定位表头行：同一行内同时出现 序号/单位/数量 标签。 */
    private int findHeaderRowIndex(List<List<String>> grid) {
        for (int i = 0; i < grid.size(); i++) {
            String joined = String.join(" ", grid.get(i));
            if (joined.contains("序号") && joined.contains("单位") && joined.contains("数量")) {
                return i;
            }
        }
        return -1;
    }

    /** 按表头标签匹配各列语义；不满足校验（首列序号/末列备注/含单位数量/语义唯一）时返回 null。 */
    private List<Semantic> semanticsFromHeader(List<String> headerRow) {
        List<Semantic> semantics = new ArrayList<>();
        for (String cell : headerRow) {
            Semantic semantic = MaterialTableModels.matchSemantic(cell.replace(" ", ""));
            if (semantic == null) {
                continue;
            }
            if (semantics.contains(semantic)) {
                return null;
            }
            semantics.add(semantic);
        }
        if (semantics.size() < 4
                || semantics.get(0) != Semantic.SERIAL
                || semantics.get(semantics.size() - 1) != Semantic.REMARK
                || !semantics.contains(Semantic.UNIT)
                || !semantics.contains(Semantic.QUANTITY)) {
            return null;
        }
        return semantics;
    }

    /** 数据行的主导列数（出现次数最多的列数，≥4 才有效），封面行与标题行列数少不参与。 */
    private int dominantColumnCount(List<List<String>> grid) {
        Map<Integer, Integer> counts = new HashMap<>();
        for (List<String> row : grid) {
            if (row.size() >= 4) {
                counts.merge(row.size(), 1, Integer::sum);
            }
        }
        int best = -1;
        int bestCount = 0;
        for (Map.Entry<Integer, Integer> entry : counts.entrySet()) {
            if (entry.getValue() > bestCount) {
                best = entry.getKey();
                bestCount = entry.getValue();
            }
        }
        return best;
    }

    /** 无表头时按列数取默认布局；列数不在已知模板范围时返回 null。 */
    private List<Semantic> defaultLayout(int columnCount) {
        Semantic[] layout = DEFAULT_LAYOUTS.get(columnCount);
        return layout == null ? null : List.of(layout);
    }

    /** 判断是否数据行：列数与语义布局一致且不全为空（封面、标题、签章、空白行被排除）。 */
    private boolean isDataRow(List<String> cells, List<Semantic> semantics) {
        if (semantics == null || cells.size() != semantics.size()) {
            return false;
        }
        return !cells.stream().allMatch(String::isEmpty);
    }

    /**
     * 从首个数据行之前的行中提取封面信息：表类型、表专业、工程名称。
     * 与 PDF 解析口径一致：表类型为"材料表/设备表"等标题，工程名称为项目名称标题文字。
     */
    private void extractCover(ParsedHeader header, List<List<String>> grid, int firstDataIndex) {
        int bound = firstDataIndex < 0 ? grid.size() : firstDataIndex;
        String projectName = "";
        for (int i = 0; i < bound; i++) {
            String joined = String.join(" ", grid.get(i));
            for (String cell : grid.get(i)) {
                if (cell.isEmpty()) {
                    continue;
                }
                String stripped = cell.replace(" ", "");
                if (header.tableType == null && stripped.length() <= 6
                        && MaterialTableModels.TABLE_TYPE_PATTERN.matcher(stripped).matches()) {
                    Matcher matcher = MaterialTableModels.TABLE_TYPE_PATTERN.matcher(stripped);
                    if (matcher.matches()) {
                        header.tableType = matcher.group(1);
                    }
                }
                if (header.specialty == null) {
                    Matcher matcher = SPECIALTY_PATTERN.matcher(joined);
                    if (matcher.find()) {
                        header.specialty = matcher.group(1).replaceAll("\\s+", "");
                    }
                }
                if (projectName.isEmpty() && isProjectNameCell(cell)) {
                    projectName = cell;
                }
            }
        }
        header.projectSection = projectName;
    }

    /** 判断封面单元格是否为工程名称：无键值冒号、长度足够、非表头标签且不含封面固定栏目关键字。 */
    private boolean isProjectNameCell(String cell) {
        if (cell.length() < 8 || cell.contains("：") || cell.contains(":")) {
            return false;
        }
        // 排除表头行标签单元格（如"名称、规格及标准号"），避免被误认为工程名称。
        if (MaterialTableModels.matchSemantic(cell.replace(" ", "")) != null) {
            return false;
        }
        for (String keyword : COVER_EXCLUDE_KEYWORDS) {
            if (cell.contains(keyword)) {
                return false;
            }
        }
        return true;
    }

    /** 按列语义把一行单元格映射为原始行；序号/位号/描述/单位/数量全空的非数据行返回 null。 */
    private ParsedRow toParsedRow(List<String> cells, List<Semantic> semantics) {
        ParsedRow row = new ParsedRow();
        for (int i = 0; i < semantics.size(); i++) {
            String value = i < cells.size() ? cells.get(i) : "";
            switch (semantics.get(i)) {
                case SERIAL -> row.serialNo = value;
                case EQUIPMENT_TAG -> row.equipmentTag = value;
                case DESCRIPTION -> row.description = value;
                case NOMINAL_SIZE -> row.nominalSize = value;
                case UNIT -> row.unit = value;
                case QUANTITY -> row.quantity = value;
                case UNIT_WEIGHT -> row.unitWeight = value;
                case TOTAL_WEIGHT -> row.totalWeight = value;
                case REMARK -> row.remark = value;
            }
        }
        if (isEmpty(row.serialNo) && isEmpty(row.equipmentTag) && isEmpty(row.description)
                && isEmpty(row.unit) && isEmpty(row.quantity)) {
            return null;
        }
        return row;
    }

    /** 空串判断（ParsedRow 各列默认 null）。 */
    private boolean isEmpty(String value) {
        return value == null || value.isEmpty();
    }
}
