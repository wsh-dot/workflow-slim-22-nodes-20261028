package com.cq.design.smartcost.modules.project.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.project.model.Project;
import org.apache.ibatis.annotations.Mapper;

/** sc_project 数据访问。 */
@Mapper
public interface ProjectDao extends BaseMapper<Project> {
}
