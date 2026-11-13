package com.cq.design.smartcost.modules.raw.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.raw.model.FileItem;
import org.apache.ibatis.annotations.Mapper;

/** sc_file_item 数据访问。 */
@Mapper
public interface FileItemDao extends BaseMapper<FileItem> {
}
