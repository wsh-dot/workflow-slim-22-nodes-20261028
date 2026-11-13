package com.cq.design.smartcost.modules.project.dao;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.cq.design.smartcost.modules.project.model.ProjectFile;
import org.apache.ibatis.annotations.Mapper;

/** sc_file 数据访问。 */
@Mapper
public interface ProjectFileDao extends BaseMapper<ProjectFile> {
}
