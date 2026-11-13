package com.cq.design.smartcost.modules.ai.model;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

/** 对应数据库表 sc_ai_python_task：发给 Python 端的 AI 处理任务。 */
@TableName("sc_ai_python_task")
@Data
public class AiPythonTask {
    @TableId(type = IdType.INPUT)
    private String id;
    @TableField("request_id")
    private String requestId;
    @TableField("project_id")
    private String projectId;
    @TableField("batch_id")
    private String batchId;
    /** 任务类型：工程量结构树构建、定额匹配、价格匹配，取组价节点编码（0901/0902/...）。 */
    @TableField("task_type")
    private String taskType;
    /** 任务状态：0 执行中、1 已生成。 */
    private String status;
    /** 失败或超时原因。 */
    @TableField("error_message")
    private String errorMessage;
    /**
     * 创建人 UUID：由 UuidIdMetaObjectHandler 自动填充。
     * 注意：MP 只有在实体存在 fill = FieldFill.INSERT 字段时才会调用填充器，
     * 因此审计字段必须标注 fill，否则 create_user_id 永远为空。
     */
    @TableField(value = "create_user_id", fill = FieldFill.INSERT)
    private String createUserId;
    @TableField(value = "create_org_id", fill = FieldFill.INSERT)
    private String createOrgId;
    @TableField(value = "create_date", fill = FieldFill.INSERT)
    private String createDate;
}
