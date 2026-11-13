package com.cq.design.smartcost.modules.raw.model;


import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/** 对应数据库表 sc_file_raw，料表解析原始行。 */
@TableName("sc_file_raw")
@Data
public class FileRaw {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("file_id")
    private String fileId;
    /** 料表序号原始值。 */
    @TableField("serial_no")
    private String serialNo;
    /** 设备位号原始值，非设备表可为空。 */
    @TableField("equipment_tag")
    private String equipmentTag;
    /** 描述或名称、规格及标准号原始值。 */
    private String description;
    /** 公称尺寸原始值，非该类料表可为空。 */
    @TableField("nominal_size")
    private String nominalSize;
    /** 料表单位原始值。 */
    private String unit;
    /** 料表数量原始值，按文本保存以保留原格式。 */
    private String quantity;
    /** 单件或单台质量原始值，非该类料表可为空。 */
    @TableField("unit_weight")
    private String unitWeight;
    /** 总质量原始值，非该类料表可为空。 */
    @TableField("total_weight")
    private String totalWeight;
    /** 料表备注原始值。 */
    private String remark;
    /** 来源料表行顺序，空序号行也保留原顺序。 */
    private Integer orderno;
}
