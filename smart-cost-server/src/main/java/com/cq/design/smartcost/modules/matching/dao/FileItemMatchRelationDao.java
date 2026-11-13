package com.cq.design.smartcost.modules.matching.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.matching.model.FileItemMatchRelation;
import org.apache.ibatis.annotations.Mapper;

/** 定额匹配结果关联关系数据访问。 */
@Mapper
public interface FileItemMatchRelationDao extends BaseMapper<FileItemMatchRelation> {
}
