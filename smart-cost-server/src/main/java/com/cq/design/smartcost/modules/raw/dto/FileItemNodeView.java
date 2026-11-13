package com.cq.design.smartcost.modules.raw.dto;

import lombok.Data;

/** 工程量结构项视图：对应 sc_file_item，线性列表（设备/主材分类展示由前端合成文件夹完成）。 */
@Data
public class FileItemNodeView {
    /** 结构项 UUID。 */
    private String id;
    /** 来源料表文件 UUID；合成层节点为空。 */
    private String fileId;
    /** 父结构项 UUID，分组根节点为空。 */
    private String parentId;
    /** 同级排序号。 */
    private Integer sortNo;
    /** 节点类型：EQUIPMENT（设备）或 MATERIAL（主材）。 */
    private String type;
    /** 节点编码。 */
    private String code;
    /** 名称。 */
    private String name;
    /** 规格型号。 */
    private String specification;
    /** 计量单位。 */
    private String unit;
    /** 工程量。 */
    private String quantity;
    /** 备注。 */
    private String remark;
    /** CBS 挂接状态（字典14）：1401 已命中、1402 未命中、1403 已处理。 */
    private String cbsMatchStatus;
    /** 挂接方式（字典15）：1501 自动、1502 人工。 */
    private String cbsMatchMethod;
    /** 挂接的项目 CBS UUID；未挂接为空。 */
    private String projectCbsId;
    /** 料表标题（分组节点展示，取表头工程路径或文件名）。 */
    private String fileTitle;
    /** 所属专业名称（取料表表头解析结果）。 */
    private String specialty;
    /** 来源描述：末级项为“文件名 / 第N项”。 */
    private String source;
}
