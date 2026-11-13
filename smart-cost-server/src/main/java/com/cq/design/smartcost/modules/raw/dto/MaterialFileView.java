package com.cq.design.smartcost.modules.raw.dto;

import com.cq.design.smartcost.modules.file.model.FileInfo;
import lombok.Data;
import lombok.EqualsAndHashCode;

/** 料表文件列表视图：文件登记信息 + 分析状态（sc_file_item 是否存在该文件的关联数据）。 */
@Data
@EqualsAndHashCode(callSuper = true)
public class MaterialFileView extends FileInfo {
    /** true=已分析（sc_file_item 存在关联数据）；false=未分析。 */
    private boolean analyzed;
}
