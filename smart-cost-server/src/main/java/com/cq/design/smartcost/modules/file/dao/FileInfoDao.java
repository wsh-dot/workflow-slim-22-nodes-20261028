package com.cq.design.smartcost.modules.file.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.file.model.FileInfo;
import org.apache.ibatis.annotations.Mapper;

/** 业务文件登记数据访问。 */
@Mapper
public interface FileInfoDao extends BaseMapper<FileInfo> {
}
