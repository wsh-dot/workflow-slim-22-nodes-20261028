package com.cq.design.smartcost.modules.raw.service;

import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedHeader;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedRow;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.ParsedTable;
import com.cq.design.smartcost.modules.raw.service.MaterialTableModels.Semantic;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;
import org.springframework.stereotype.Component;

import java.awt.geom.Point2D;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 料表 PDF 解析器（设计院固定模板，兼容多种列布局）。
 *
 * <p>支持的料表格式（由表头标签自动识别，不依赖固定列数）：</p>
 * <ul>
 * <li>设备表：序号 / 设备位号 / 名称及规格 / 单位 / 数量 / 单台质量(kg) / 总质量(kg) / 备注</li>
 * <li>材料表：序号 / 描述 / 公称尺寸 / 单位 / 数量 / 备注</li>
 * <li>名称规格表：序号 / 名称、规格及标准号 / 单位 / 数量 / 单件质量(kg) / 总质量(kg) / 备注</li>
 * </ul>
 *
 * <p>解析产出为原始行（按页序与行序编排 orderno），空序号行也按原样保留，
 * 层级关系由后续业务根据序号原始值（中文数字/阿拉伯数字/无序号）自行推导。</p>
 *
 * <p>实现方式：用 PDFBox 提取每个字符的页面坐标，按纵坐标聚成行；再用图形引擎收集表格竖线
 * 作为列分隔，把按列输出的 PDF 内容还原成"一行一条记录"的结构，避免纯文本流按列分组的错位。</p>
 */
@Component
public class MaterialTablePdfParser {

    /** 行聚类容差（pt）：同一行内字符纵坐标偏差小于该值视为同一行。 */
    private static final float ROW_TOLERANCE = 5.0f;
    /** 同一单词内字符最大横向间隔（pt）。 */
    private static final float WORD_GAP = 2.0f;
    /** 单元格内相邻单词间距超过该值时补一个空格（pt）。 */
    private static final float CELL_SPACE_GAP = 3.5f;
    /** 竖线聚类容差（pt）。 */
    private static final float SEPARATOR_TOLERANCE = 2.0f;
    /** 竖线最小长度（pt）：过滤短刻度线，只保留表格网格线。 */
    private static final float SEPARATOR_MIN_LENGTH = 30.0f;
    /** 表头合并容差（pt）：两层表头（如"单台质量(kg)"与"序号"分层）纵向间距小于该值时合并。 */
    private static final float HEADER_MERGE_TOLERANCE = 10.0f;
    private static final Pattern SPECIALTY_PATTERN = Pattern.compile("专业\\s*[：:]\\s*([^\\s：:]+)");
    private static final Pattern PAGE_NO_PATTERN = Pattern.compile("第\\s*\\d+\\s*页");
    private static final Pattern TOTAL_PAGE_PATTERN = Pattern.compile("共\\s*\\d+\\s*页");
    private static final Pattern CERT_NO_PATTERN = Pattern.compile("[A-Za-z]+\\d+");
    /** 签章行压缩文本：整行仅由签章字组成（字间被版框拆散为单字时也能识别）。 */
    private static final Pattern COMPACT_SIG_PATTERN = Pattern.compile("^[编制校对审核审定]+$");
    /** 封面固定文字（公司名、证书号、签章栏等），不作为表名称。 */
    private static final String[] COVER_EXCLUDE_KEYWORDS =
            {"有限公司", "证书号", "编制", "校对", "审核", "审定"};

    /** 单词：一行内按横向间隔聚成的连续字符。 */
    private record Word(float x0, float x1, String text) {
        float center() { return (x0 + x1) / 2; }
    }

    /** 行：纵坐标聚类的单词集合。 */
    private static final class Row {
        float y;
        List<Word> words = new ArrayList<>();
    }

    /** 表头列：语义 + 标签单词（用于推导列边界）。 */
    private record LabelColumn(Semantic semantic, Word label) { }

    /** 收集页面竖线段的图形引擎。 */
    private static final class GridLineEngine extends PDFGraphicsStreamEngine {
        /** 线段集合：[x0, y0, x1, y1]，用户空间坐标。 */
        private final List<float[]> segments = new ArrayList<>();
        private float currentX;
        private float currentY;
        private float pathStartX;
        private float pathStartY;

        GridLineEngine(PDPage page) {
            super(page);
        }

        List<Float> verticalSeparators() {
            // 竖线 x 坐标聚类：同列多条线段归为一个分隔位置。
            List<Float> xs = new ArrayList<>();
            for (float[] segment : segments) {
                if (Math.abs(segment[0] - segment[2]) < 0.5f
                        && Math.abs(segment[1] - segment[3]) >= SEPARATOR_MIN_LENGTH) {
                    xs.add(segment[0]);
                }
            }
            xs.sort(Comparator.comparingDouble(Float::doubleValue));
            List<Float> separators = new ArrayList<>();
            for (float x : xs) {
                if (separators.isEmpty() || x - separators.get(separators.size() - 1) > SEPARATOR_TOLERANCE) {
                    separators.add(x);
                }
            }
            return separators;
        }

        @Override
        public void appendRectangle(Point2D p0, Point2D p1, Point2D p2, Point2D p3) {
            addSegment(p0, p1);
            addSegment(p1, p2);
            addSegment(p2, p3);
            addSegment(p3, p0);
        }

        @Override
        public void drawImage(org.apache.pdfbox.pdmodel.graphics.image.PDImage pdImage) { }

        @Override
        public void clip(int windingRule) { }

        @Override
        public void shadingFill(org.apache.pdfbox.cos.COSName shadingName) { }

        @Override
        public void fillAndStrokePath(int windingRule) { }

        @Override
        public void fillPath(int windingRule) { }

        @Override
        public void strokePath() { }

        @Override
        public Point2D getCurrentPoint() {
            return new Point2D.Float(currentX, currentY);
        }

        @Override
        public void moveTo(float x, float y) {
            currentX = x;
            currentY = y;
            pathStartX = x;
            pathStartY = y;
        }

        @Override
        public void lineTo(float x, float y) {
            addSegment(new Point2D.Float(currentX, currentY), new Point2D.Float(x, y));
            currentX = x;
            currentY = y;
        }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2, float x3, float y3) {
            // 曲线不产生表格网格线，仅推进当前点。
            currentX = x3;
            currentY = y3;
        }

        @Override
        public void closePath() {
            // 闭合路径补最后一条边（如 Excel 导出的边框矩形）。
            addSegment(new Point2D.Float(currentX, currentY), new Point2D.Float(pathStartX, pathStartY));
            currentX = pathStartX;
            currentY = pathStartY;
        }

        @Override
        public void endPath() { }

        private void addSegment(Point2D from, Point2D to) {
            segments.add(new float[] {(float) from.getX(), (float) from.getY(),
                    (float) to.getX(), (float) to.getY()});
        }
    }

    /* 封面解析结果、数据行与整体结构见 {@link MaterialTableModels}（PDF/Word 共用模型）。 */
    /** 收集页面字符坐标的文本剥离器。 */
    private static final class PositionStripper extends PDFTextStripper {
        private final List<TextPosition> collected = new ArrayList<>();

        PositionStripper() {
            super();
        }

        @Override
        protected void writeString(String text, List<TextPosition> textPositions) {
            collected.addAll(textPositions);
        }

        List<TextPosition> readPage(PDDocument document, int pageNo) throws IOException {
            collected.clear();
            setStartPage(pageNo);
            setEndPage(pageNo);
            getText(document);
            return collected;
        }
    }

    /** 解析料表 PDF：第 1 页封面 + 第 2 页起的数据行。 */
    public ParsedTable parse(byte[] content) throws IOException {
        try (PDDocument document = Loader.loadPDF(content)) {
            PositionStripper stripper = new PositionStripper();
            int pageCount = document.getNumberOfPages();
            ParsedTable result = new ParsedTable();
            for (int pageNo = 1; pageNo <= pageCount; pageNo++) {
                List<Row> rows = extractRows(stripper, document, pageNo);
                if (pageNo == 1) {
                    parseCover(result.header, rows);
                } else {
                    appendRows(result.rows, rows, document.getPage(pageNo - 1));
                }
            }
            return result;
        }
    }

    /** 提取一页的文本行：字符 → 行聚类 → 行内按横向间隔聚成单词。 */
    private List<Row> extractRows(PositionStripper stripper, PDDocument document, int pageNo)
            throws IOException {
        List<TextPosition> positions = new ArrayList<>();
        for (TextPosition position : stripper.readPage(document, pageNo)) {
            if (position.getUnicode() == null || position.getUnicode().isBlank()) {
                continue;
            }
            positions.add(position);
        }
        // 先按纵坐标聚类成行，再在行内按横坐标排序聚单词。
        positions.sort(Comparator.comparingDouble(TextPosition::getYDirAdj));
        List<Row> rows = new ArrayList<>();
        for (TextPosition position : positions) {
            float y = position.getYDirAdj();
            Row row;
            if (!rows.isEmpty() && Math.abs(rows.get(rows.size() - 1).y - y) <= ROW_TOLERANCE) {
                row = rows.get(rows.size() - 1);
                // 行中心随成员增量更新，避免斜排文本越聚越偏。
                row.y = (row.y * (row.words.size()) + y) / (row.words.size() + 1);
            } else {
                row = new Row();
                row.y = y;
                rows.add(row);
            }
            row.words.add(new Word(position.getXDirAdj(),
                    position.getXDirAdj() + position.getWidthDirAdj(), position.getUnicode()));
        }
        for (Row row : rows) {
            row.words.sort(Comparator.comparing(Word::x0));
            // 行内字符按间隔聚成单词：连续字母数字与 CJK 成词，供标签匹配与列切分使用。
            row.words = mergeWords(row.words);
        }
        return rows;
    }

    /** 将行内相邻字符聚成单词：横向间隔小于 WORD_GAP 视为同一单词。 */
    private List<Word> mergeWords(List<Word> glyphs) {
        List<Word> words = new ArrayList<>();
        StringBuilder pending = new StringBuilder();
        float pendingStart = 0;
        float lastEnd = Float.NEGATIVE_INFINITY;
        for (Word glyph : glyphs) {
            if (!pending.isEmpty() && glyph.x0() - lastEnd > WORD_GAP) {
                words.add(new Word(pendingStart, lastEnd, pending.toString()));
                pending.setLength(0);
            }
            if (pending.isEmpty()) {
                pendingStart = glyph.x0();
            }
            pending.append(glyph.text());
            lastEnd = glyph.x1();
        }
        if (!pending.isEmpty()) {
            words.add(new Word(pendingStart, lastEnd, pending.toString()));
        }
        return words;
    }

    /**
     * 解析封面（第 1 页）：表类型、表专业、表名称。
     * 封面键值与标题常被版框拆成多个单词（如"专"+"业："+"消防"、签章"编 制 校 对..."），
     * 因此先用行压缩文本（去空格）识别表类型、专业与整行噪音，再按单词收集标题区文字。
     */
    private void parseCover(ParsedHeader header, List<Row> rows) {
        StringBuilder section = new StringBuilder();
        for (Row row : rows) {
            String compact = joinText(row.words).replace(" ", "");
            if (compact.isEmpty()) {
                continue;
            }
            // 表类型与专业从压缩文本识别："专 业：消防"这类拆分键也能命中。
            if (header.tableType == null) {
                Matcher matcher = MaterialTableModels.TABLE_TYPE_PATTERN.matcher(compact);
                if (matcher.find()) {
                    header.tableType = matcher.group(1);
                }
            }
            if (header.specialty == null) {
                Matcher matcher = SPECIALTY_PATTERN.matcher(compact);
                if (matcher.find()) {
                    header.specialty = matcher.group(1).trim();
                }
            }
            // 整行排除：大字表类型标题、页码版次行、签章行（拆散单字无法逐词排除）。
            if (isCoverNoiseRow(compact)) {
                continue;
            }
            appendCoverTitleWords(row.words, section);
        }
        header.projectSection = section.toString().trim();
    }

    /** 封面整行排除：整行即表类型标题（含字间拆散的"设 备 表"）、页码/版次行、签章行。 */
    private boolean isCoverNoiseRow(String compact) {
        if (MaterialTableModels.TABLE_TYPE_PATTERN.matcher(compact).matches()) {
            return true;
        }
        if (PAGE_NO_PATTERN.matcher(compact).find() || TOTAL_PAGE_PATTERN.matcher(compact).find()) {
            return true;
        }
        return COMPACT_SIG_PATTERN.matcher(compact).matches();
    }

    /**
     * 将封面行中属于工程名称标题区的单词追加到标题文本。
     * 键值区从首个含冒号的单词起整体跳过；其前一个 ≤2 字的单词通常是拆散的键字
     * （如"专 业："的"专"、"阶 段："的"阶"），一并跳过，冒号前的长标题单词正常保留。
     */
    private void appendCoverTitleWords(List<Word> words, StringBuilder section) {
        int colonIndex = -1;
        for (int i = 0; i < words.size(); i++) {
            String text = words.get(i).text().trim();
            if (text.contains("：") || text.contains(":")) {
                colonIndex = i;
                break;
            }
        }
        int start = words.size();
        if (colonIndex >= 0) {
            start = colonIndex;
            if (colonIndex > 0 && words.get(colonIndex - 1).text().trim().length() <= 2) {
                start = colonIndex - 1;
            }
        }
        for (int i = 0; i < start; i++) {
            String text = words.get(i).text().trim();
            if (!text.isEmpty() && isCoverTitleWord(text)) {
                if (!section.isEmpty()) {
                    section.append(' ');
                }
                section.append(text);
            }
        }
    }

    /** 判断封面单词是否属于工程名称标题区（排除键值对、表类型标题、公司信息、页码版次与签章栏）。 */
    private boolean isCoverTitleWord(String text) {
        if (text.contains("：") || text.contains(":")) {
            return false;
        }
        if (MaterialTableModels.TABLE_TYPE_PATTERN.matcher(text).matches()) {
            return false;
        }
        if (PAGE_NO_PATTERN.matcher(text).find() || TOTAL_PAGE_PATTERN.matcher(text).find()
                || text.matches(".*[A-Za-z]?版$")) {
            return false;
        }
        if (CERT_NO_PATTERN.matcher(text).matches()) {
            return false;
        }
        for (String keyword : COVER_EXCLUDE_KEYWORDS) {
            if (text.contains(keyword)) {
                return false;
            }
        }
        return true;
    }

    /** 解析数据页（第 2 页起）：按表头标签识别列语义，用表格竖线切列，逐行还原为原始行。 */
    private void appendRows(List<ParsedRow> target, List<Row> rows, PDPage page) throws IOException {
        Row headerRow = findColumnHeaderRow(rows);
        if (headerRow == null) {
            return;
        }
        List<LabelColumn> columns = locateLabelColumns(headerRow);
        if (columns == null) {
            return;
        }
        List<Float> separators = readSeparators(page);
        // 至少需要"每个标签一格 + 末列右边界"数量的竖线。
        if (separators.size() < columns.size() + 1) {
            return;
        }
        float[] columnRights = columnRightEdges(columns, separators);
        if (columnRights.length != columns.size()) {
            return;
        }
        for (Row row : rows) {
            if (row.y <= headerRow.y + ROW_TOLERANCE) {
                continue;
            }
            String[] cells = splitCells(row, columnRights);
            ParsedRow item = new ParsedRow();
            item.serialNo = cellText(columns, cells, Semantic.SERIAL);
            item.equipmentTag = cellText(columns, cells, Semantic.EQUIPMENT_TAG);
            item.description = cellText(columns, cells, Semantic.DESCRIPTION);
            item.nominalSize = cellText(columns, cells, Semantic.NOMINAL_SIZE);
            item.unit = cellText(columns, cells, Semantic.UNIT);
            item.quantity = cellText(columns, cells, Semantic.QUANTITY);
            item.unitWeight = cellText(columns, cells, Semantic.UNIT_WEIGHT);
            item.totalWeight = cellText(columns, cells, Semantic.TOTAL_WEIGHT);
            item.remark = cellText(columns, cells, Semantic.REMARK);
            if (item.serialNo.isEmpty() && item.equipmentTag.isEmpty() && item.description.isEmpty()
                    && item.unit.isEmpty() && item.quantity.isEmpty()) {
                // 签章、空白等非数据行。
                continue;
            }
            target.add(item);
        }
    }

    /**
     * 定位数据页的表头行：同时包含 序号/单位/数量 标签的行作为锚点，
     * 并合并其上下邻近的表头行——两层表头中"单台质量/总质量/备注"在锚点上方、
     * "(kg)"等单位补注在锚点下方，不合并会导致末列识别不到备注而整页跳过。
     */
    private Row findColumnHeaderRow(List<Row> rows) {
        for (int i = 0; i < rows.size(); i++) {
            Row row = rows.get(i);
            String text = joinText(row.words);
            if (text.contains("序号") && text.contains("单位") && text.contains("数量")) {
                return mergeHeaderLines(rows, i);
            }
        }
        return null;
    }

    /** 将锚点行上下 HEADER_MERGE_TOLERANCE 内的行合并为一条虚拟表头行（按横向顺序重排单词）。 */
    private Row mergeHeaderLines(List<Row> rows, int anchorIndex) {
        Row anchor = rows.get(anchorIndex);
        Row merged = new Row();
        merged.y = anchor.y;
        merged.words.addAll(anchor.words);
        for (int i = 0; i < rows.size(); i++) {
            if (i == anchorIndex || Math.abs(rows.get(i).y - anchor.y) > HEADER_MERGE_TOLERANCE) {
                continue;
            }
            merged.words.addAll(rows.get(i).words);
        }
        merged.words.sort(Comparator.comparing(Word::x0));
        return merged;
    }

    /** 表头行文本拼接（单词间以空格连接）。 */
    private String joinText(List<Word> words) {
        StringBuilder text = new StringBuilder();
        for (Word word : words) {
            if (!text.isEmpty()) {
                text.append(' ');
            }
            text.append(word.text().trim());
        }
        return text.toString();
    }

    /**
     * 识别表头行各标签的语义并按横向顺序返回。
     * 要求：首列为序号、末列为备注、各语义唯一出现，否则视为不支持的料表格式。
     */
    private List<LabelColumn> locateLabelColumns(Row headerRow) {
        List<LabelColumn> columns = new ArrayList<>();
        for (Word word : headerRow.words) {
            String text = word.text().trim();
            Semantic semantic = MaterialTableModels.matchSemantic(text);
            if (semantic == null) {
                continue;
            }
            boolean duplicated = columns.stream().anyMatch(column -> column.semantic() == semantic);
            if (duplicated) {
                return null;
            }
            columns.add(new LabelColumn(semantic, word));
        }
        if (columns.size() < 4
                || columns.get(0).semantic() != Semantic.SERIAL
                || columns.get(columns.size() - 1).semantic() != Semantic.REMARK) {
            return null;
        }
        // 料表必须具备序号/单位/数量三列，缺失视为不支持的格式，避免数量等列被并入相邻列。
        boolean hasUnit = false;
        boolean hasQuantity = false;
        for (LabelColumn column : columns) {
            hasUnit |= column.semantic() == Semantic.UNIT;
            hasQuantity |= column.semantic() == Semantic.QUANTITY;
        }
        if (!hasUnit || !hasQuantity) {
            return null;
        }
        return columns;
    }

    /** 用图形引擎收集页面表格竖线位置。 */
    private List<Float> readSeparators(PDPage page) throws IOException {
        GridLineEngine engine = new GridLineEngine(page);
        engine.processPage(page);
        return engine.verticalSeparators();
    }

    /**
     * 计算各列右边界：标签中心右侧第一条竖线。
     * 第 i 列的取值范围为 [第 i-1 列右边界, 第 i 列右边界)，首列左界为页左缘。
     */
    private float[] columnRightEdges(List<LabelColumn> columns, List<Float> separators) {
        float[] rights = new float[columns.size()];
        for (int i = 0; i < columns.size(); i++) {
            final float labelCenter = columns.get(i).label().center();
            Float edge = separators.stream()
                    .filter(separator -> separator > labelCenter)
                    .findFirst().orElse(null);
            if (edge == null) {
                return new float[0];
            }
            rights[i] = edge;
        }
        // 右边界必须严格递增，否则标签与网格不匹配。
        for (int i = 1; i < rights.length; i++) {
            if (rights[i] <= rights[i - 1]) {
                return new float[0];
            }
        }
        return rights;
    }

    /** 按列右边界把一行单词切分到各列，返回与列序对齐的单元格文本。 */
    private String[] splitCells(Row row, float[] columnRights) {
        List<List<Word>> cells = new ArrayList<>();
        for (int i = 0; i < columnRights.length; i++) {
            cells.add(new ArrayList<>());
        }
        for (Word word : row.words) {
            int column = columnRights.length - 1;
            for (int i = 0; i < columnRights.length; i++) {
                if (word.center() < columnRights[i]) {
                    column = i;
                    break;
                }
            }
            cells.get(column).add(word);
        }
        String[] texts = new String[cells.size()];
        for (int i = 0; i < cells.size(); i++) {
            texts[i] = joinCell(cells.get(i));
        }
        return texts;
    }

    /** 取指定语义列的单元格文本并去除首尾空白；该格式无此列时返回空串。 */
    private String cellText(List<LabelColumn> columns, String[] cells, Semantic semantic) {
        for (int i = 0; i < columns.size(); i++) {
            if (columns.get(i).semantic() == semantic) {
                return cells[i].trim();
            }
        }
        return "";
    }

    /** 拼接单元格文本：相邻单词间距较大时补空格，尽量还原原始可读文本。 */
    private static String joinCell(List<Word> words) {
        StringBuilder text = new StringBuilder();
        Float lastEnd = null;
        for (Word word : words) {
            if (lastEnd != null && word.x0() - lastEnd > CELL_SPACE_GAP) {
                text.append(' ');
            }
            text.append(word.text());
            lastEnd = word.x1();
        }
        return text.toString();
    }
}
