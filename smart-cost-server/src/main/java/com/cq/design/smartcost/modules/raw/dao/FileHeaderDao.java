package com.cq.design.smartcost.modules.raw.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.raw.model.FileHeader;
import org.apache.ibatis.annotations.Mapper;

/** sc_file_header 数据访问。 */
@Mapper
public interface FileHeaderDao extends BaseMapper<FileHeader> {
}
