package com.cq.design.smartcost.modules.project.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.project.model.Batch;
import org.apache.ibatis.annotations.Mapper;

/** sc_batch 数据访问。 */
@Mapper
public interface BatchDao extends BaseMapper<Batch> {
}
