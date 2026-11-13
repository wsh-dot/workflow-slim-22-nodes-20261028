-- PostgreSQL 初始表结构脚本，执行时会删除并重建本项目的全部业务表和系统管理表。
-- 注意：执行后原表数据不可恢复；请仅用于初始化数据库。
-- 时间文本统一为 UTC 格式 yyyy-MM-dd HH:mm:ss，固定 19 位；是/否使用 SMALLINT 0/1。
-- 技术主键由 Java 生成 UUID 字符串。
BEGIN;

DROP TABLE IF EXISTS
    sc_project, sc_batch, sc_ai_python_task, sc_file, sc_file_header, sc_file_raw, sc_file_item, sc_file_item_match,
    sc_file_item_match_relation, sc_file_item_match_consume, sc_history_project, sc_history_project_cbs,
    sc_history_project_item, sc_history_project_consume, sc_match_experience, sc_task,
    sc_flow_log, sc_cbs, sc_cbs_detail, sc_project_cbs, sc_price_basis, sc_de_library,
    sc_de_directory, sc_de_item, sc_de_rcj_category, sc_de_rcj, sc_de_consume, sc_price,
    sc_project_cbs_de_library, sc_qf_model, sc_qf_model_param, sc_project_qf_model,
    sc_project_qf_model_param, pb_base_option, sys_user, sys_user_category, sys_user_uid,
    sys_group, sys_group_category, sys_user_group, sys_group_permission, sys_permission,
    sys_permission_category, sys_user_permission, sys_resource, sys_resource_category,
    sys_permission_resource, sys_menu, sys_operation_log;

-- 项目表
CREATE TABLE IF NOT EXISTS sc_project (
    id varchar(36) NOT NULL,
    code varchar(40),
    name varchar(100),
    key_info varchar(1000),
    specialty_code varchar(32),
    status varchar(32),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_project PRIMARY KEY (id),
    CONSTRAINT uq_sc_project_code UNIQUE (code)
);
COMMENT ON TABLE sc_project IS '项目表';
COMMENT ON COLUMN sc_project.id IS 'Java 生成 UUID，项目主键';
COMMENT ON COLUMN sc_project.code IS '项目编码，唯一';
COMMENT ON COLUMN sc_project.name IS '项目名称';
COMMENT ON COLUMN sc_project.key_info IS '项目关键说明';
COMMENT ON COLUMN sc_project.specialty_code IS '所属专业字典编码，可为空';
COMMENT ON COLUMN sc_project.status IS '项目状态字典编码';
COMMENT ON COLUMN sc_project.create_user_id IS '创建人 UUID';
COMMENT ON COLUMN sc_project.create_org_id IS '创建机构 UUID';
COMMENT ON COLUMN sc_project.create_date IS '创建时间';

-- 批次表
CREATE TABLE IF NOT EXISTS sc_batch (
    id varchar(36) NOT NULL,
    project_id varchar(36),
    batch_no integer,
    status varchar(32),
    current_stage varchar(32),
    pricing_completed_at varchar(19),
    calculation_completed_at varchar(19),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_batch PRIMARY KEY (id),
    CONSTRAINT uq_sc_batch_project_id_batch_no UNIQUE (project_id, batch_no)
);
COMMENT ON TABLE sc_batch IS '批次表';
COMMENT ON COLUMN sc_batch.id IS 'Java 生成 UUID，批次主键';
COMMENT ON COLUMN sc_batch.project_id IS '所属项目 UUID，关联 sc_project.id';
COMMENT ON COLUMN sc_batch.batch_no IS '项目内批次号，不重复、不复用';
COMMENT ON COLUMN sc_batch.status IS '批次状态字典编码';
COMMENT ON COLUMN sc_batch.current_stage IS '当前处理节点字典编码';
COMMENT ON COLUMN sc_batch.pricing_completed_at IS '组价完成时间';
COMMENT ON COLUMN sc_batch.calculation_completed_at IS '概算计算完成时间';
COMMENT ON COLUMN sc_batch.create_user_id IS '创建人 UUID';
COMMENT ON COLUMN sc_batch.create_org_id IS '创建机构 UUID';
COMMENT ON COLUMN sc_batch.create_date IS '创建时间';

-- AI 异步任务记录表
CREATE TABLE IF NOT EXISTS sc_ai_python_task (
    id varchar(36) NOT NULL,
    request_id varchar(36) NOT NULL,
    project_id varchar(36) NOT NULL,
    batch_id varchar(36) NOT NULL,
    task_type varchar(32) NOT NULL,
    status varchar(16) NOT NULL,
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19) NOT NULL,
    error_message varchar(1000),
    CONSTRAINT pk_sc_ai_python_task PRIMARY KEY (id),
    CONSTRAINT uq_sc_ai_python_task_request_id UNIQUE (request_id)
);
COMMENT ON TABLE sc_ai_python_task IS 'AI 异步任务记录表';
COMMENT ON COLUMN sc_ai_python_task.id IS 'Java 生成 UUID，任务主键';
COMMENT ON COLUMN sc_ai_python_task.request_id IS '跨服务任务请求 ID，唯一';
COMMENT ON COLUMN sc_ai_python_task.project_id IS '所属项目 UUID，关联 sc_project.id';
COMMENT ON COLUMN sc_ai_python_task.batch_id IS '所属批次 UUID，关联 sc_batch.id';
COMMENT ON COLUMN sc_ai_python_task.task_type IS '任务类型：工程量结构树挂接、定恩匹配、价格匹配';
COMMENT ON COLUMN sc_ai_python_task.status IS '任务状态';
COMMENT ON COLUMN sc_ai_python_task.create_date IS '任务创建时间，UTC 格式 yyyy-MM-dd HH:mm:ss';
COMMENT ON COLUMN sc_ai_python_task.error_message IS '失败或超时原因';

-- 文件表
CREATE TABLE IF NOT EXISTS sc_file (
    id varchar(36) NOT NULL,
    master_type varchar(32),
    master_id varchar(36),
    batch_no integer,
    type varchar(32),
    status varchar(32),
    original_name varchar(255),
    stored_name varchar(255),
    file_path varchar(500),
    extension varchar(20),
    mime_type varchar(100),
    size bigint,
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_file PRIMARY KEY (id)
);
COMMENT ON TABLE sc_file IS '文件表';
COMMENT ON COLUMN sc_file.id IS 'Java 生成 UUID，文件主键';
COMMENT ON COLUMN sc_file.master_type IS '归属对象类型字典编码：PROJECT 或 BATCH';
COMMENT ON COLUMN sc_file.master_id IS '项目 UUID 或批次 UUID；由 Java 按 master_type 校验';
COMMENT ON COLUMN sc_file.batch_no IS '批次文件填写所属 sc_batch.batch_no；项目文件为空';
COMMENT ON COLUMN sc_file.type IS '文件类型字典编码';
COMMENT ON COLUMN sc_file.status IS '文件状态字典编码';
COMMENT ON COLUMN sc_file.original_name IS '用户上传的原始文件名';
COMMENT ON COLUMN sc_file.stored_name IS '程序生成的实际存储文件名';
COMMENT ON COLUMN sc_file.file_path IS '相对于文件根目录的目录路径';
COMMENT ON COLUMN sc_file.extension IS '文件扩展名';
COMMENT ON COLUMN sc_file.mime_type IS '文件媒体类型';
COMMENT ON COLUMN sc_file.size IS '文件大小，单位字节';
COMMENT ON COLUMN sc_file.create_user_id IS '上传人 UUID';
COMMENT ON COLUMN sc_file.create_org_id IS '上传机构 UUID';
COMMENT ON COLUMN sc_file.create_date IS '上传时间';

-- 料表表头解析表
CREATE TABLE IF NOT EXISTS sc_file_header (
    id varchar(36) NOT NULL,
    file_id varchar(36),
    table_type varchar(32),
    specialty_name varchar(100),
    project_section varchar(1000),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_file_header PRIMARY KEY (id),
    CONSTRAINT uq_sc_file_header_file_id UNIQUE (file_id)
);
COMMENT ON TABLE sc_file_header IS '料表表头解析表';
COMMENT ON COLUMN sc_file_header.id IS 'Java 生成 UUID，表头主键';
COMMENT ON COLUMN sc_file_header.file_id IS '来源文件 UUID，关联 sc_file.id，唯一';
COMMENT ON COLUMN sc_file_header.table_type IS '表类型字典编码，如设备表、主材表';
COMMENT ON COLUMN sc_file_header.specialty_name IS '解析出的专业名称';
COMMENT ON COLUMN sc_file_header.project_section IS '工程名称路径，多行内容使用统一分隔符拼接';
COMMENT ON COLUMN sc_file_header.create_user_id IS '创建人';
COMMENT ON COLUMN sc_file_header.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_file_header.create_date IS '创建时间';

-- 料表解析原始行表
CREATE TABLE IF NOT EXISTS sc_file_raw (
    id varchar(36) NOT NULL,
    file_id varchar(36) NOT NULL,
    serial_no varchar(100),
    equipment_tag varchar(200),
    description varchar(2000),
    nominal_size varchar(500),
    unit varchar(100),
    quantity varchar(500),
    unit_weight varchar(100),
    total_weight varchar(100),
    remark varchar(2000),
    orderno integer NOT NULL,
    CONSTRAINT pk_sc_file_raw PRIMARY KEY (id),
    CONSTRAINT uq_sc_file_raw_file_orderno UNIQUE (file_id, orderno)
);
COMMENT ON TABLE sc_file_raw IS '料表解析原始行表';
COMMENT ON COLUMN sc_file_raw.id IS 'Java 生成 UUID，原始行主键';
COMMENT ON COLUMN sc_file_raw.file_id IS '来源文件 UUID，关联 sc_file.id';
COMMENT ON COLUMN sc_file_raw.serial_no IS '料表序号原始值';
COMMENT ON COLUMN sc_file_raw.equipment_tag IS '设备位号原始值，非设备表可为空';
COMMENT ON COLUMN sc_file_raw.description IS '描述或名称、规格及标准号原始值';
COMMENT ON COLUMN sc_file_raw.nominal_size IS '公称尺寸原始值，非该类料表可为空';
COMMENT ON COLUMN sc_file_raw.unit IS '料表单位原始值';
COMMENT ON COLUMN sc_file_raw.quantity IS '料表数量原始值，按文本保存以保留原格式';
COMMENT ON COLUMN sc_file_raw.unit_weight IS '单件或单台质量原始值，非该类料表可为空';
COMMENT ON COLUMN sc_file_raw.total_weight IS '总质量原始值，非该类料表可为空';
COMMENT ON COLUMN sc_file_raw.remark IS '料表备注原始值';
COMMENT ON COLUMN sc_file_raw.orderno IS '来源料表行顺序，空序号行也保留原顺序';

-- 工程量结构项表
CREATE TABLE IF NOT EXISTS sc_file_item (
    id varchar(36) NOT NULL,
    file_id varchar(36),
    project_cbs_id varchar(36),
    parent_id varchar(36),
    sort_no integer,
    type varchar(32),
    code varchar(64),
    name varchar(2000),
    specification varchar(2000),
    unit varchar(50),
    quantity numeric(18,6),
    remark varchar(2000),
    cbs_match_status varchar(32),
    cbs_match_method varchar(32),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_file_item PRIMARY KEY (id)
);
COMMENT ON TABLE sc_file_item IS '工程量结构项表';
COMMENT ON COLUMN sc_file_item.id IS 'Java 生成 UUID，结构项主键';
COMMENT ON COLUMN sc_file_item.file_id IS '来源文件 UUID，关联 sc_file.id';
COMMENT ON COLUMN sc_file_item.project_cbs_id IS '所属项目 CBS 单位工程节点 UUID，关联 sc_project_cbs.id；未挂接时为空';
COMMENT ON COLUMN sc_file_item.parent_id IS '父工程结构项 UUID，设备、主材分组节点的父级为空';
COMMENT ON COLUMN sc_file_item.sort_no IS '同级排序号，用于页面显示顺序';
COMMENT ON COLUMN sc_file_item.type IS '节点类型字典编码：SUBSECTION、EQUIPMENT、MATERIAL';
COMMENT ON COLUMN sc_file_item.code IS '节点编码；设备、主材分组使用固定编码';
COMMENT ON COLUMN sc_file_item.name IS '节点名称';
COMMENT ON COLUMN sc_file_item.specification IS '规格型号';
COMMENT ON COLUMN sc_file_item.unit IS '计量单位';
COMMENT ON COLUMN sc_file_item.quantity IS '工程量，分组节点可为空';
COMMENT ON COLUMN sc_file_item.remark IS '备注';
COMMENT ON COLUMN sc_file_item.cbs_match_status IS 'CBS 匹配状态字典编码';
COMMENT ON COLUMN sc_file_item.cbs_match_method IS 'CBS 匹配方式，如规则匹配、语义匹配、人工调整';
COMMENT ON COLUMN sc_file_item.create_user_id IS '创建人';
COMMENT ON COLUMN sc_file_item.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_file_item.create_date IS '创建时间';

-- 工程量项定额/指标匹配结果表
CREATE TABLE IF NOT EXISTS sc_file_item_match (
    id varchar(36) NOT NULL,
    file_item_id varchar(36),
    de_library_id varchar(36),
    de_item_id varchar(36),
    is_main integer,
    code varchar(100),
    name varchar(500),
    unit varchar(50),
    formula varchar(2000),
    quantity numeric(18,6),
    base_price numeric(18,6),
    cl_fee numeric(18,6),
    rg_fee numeric(18,6),
    jx_fee numeric(18,6),
    zc_fee numeric(18,6),
    sb_fee numeric(18,6),
    match_status varchar(32),
    match_method varchar(32),
    match_score numeric(8,6),
    material_handling varchar(32),
    match_remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_file_item_match PRIMARY KEY (id)
);
COMMENT ON TABLE sc_file_item_match IS '工程量项定额/指标匹配结果表';
COMMENT ON COLUMN sc_file_item_match.id IS 'Java 生成 UUID，匹配结果主键';
COMMENT ON COLUMN sc_file_item_match.file_item_id IS '来源工程量结构项 UUID，关联 sc_file_item.id；多来源汇总的关联定额可为空';
COMMENT ON COLUMN sc_file_item_match.de_library_id IS '使用的定额/指标库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_file_item_match.de_item_id IS '命中的定额/指标 UUID，关联 sc_de_item.id；未匹配或升级为独立项时为空';
COMMENT ON COLUMN sc_file_item_match.is_main IS '是否主定额：0=非主定额，1=主定额';
COMMENT ON COLUMN sc_file_item_match.code IS '命中定额/指标编号快照';
COMMENT ON COLUMN sc_file_item_match.name IS '命中定额/指标名称快照';
COMMENT ON COLUMN sc_file_item_match.unit IS '定额/指标单位';
COMMENT ON COLUMN sc_file_item_match.formula IS '定额工程量计算式，可人工修改';
COMMENT ON COLUMN sc_file_item_match.quantity IS '计算后的定额工程量，可人工修改';
COMMENT ON COLUMN sc_file_item_match.base_price IS '命中定额/指标时先取基础基价，消耗挂接或调整后重新汇总；未匹配或升级为独立项时保存设备/主材当前价格';
COMMENT ON COLUMN sc_file_item_match.cl_fee IS '材料消耗金额汇总，初始化时取基础数据';
COMMENT ON COLUMN sc_file_item_match.rg_fee IS '人工消耗金额汇总，初始化时取基础数据';
COMMENT ON COLUMN sc_file_item_match.jx_fee IS '机械消耗金额汇总，初始化时取基础数据';
COMMENT ON COLUMN sc_file_item_match.zc_fee IS '主材消耗金额汇总';
COMMENT ON COLUMN sc_file_item_match.sb_fee IS '设备消耗金额汇总';
COMMENT ON COLUMN sc_file_item_match.match_status IS '匹配状态字典编码：MATCHED、UNMATCHED、RESTORED（升级还原）';
COMMENT ON COLUMN sc_file_item_match.match_method IS '匹配方式字典编码：LLM、RULE、LLM_RULE、MANUAL';
COMMENT ON COLUMN sc_file_item_match.match_score IS '系统计算的匹配得分，可为空；用于阈值判断和问题排查';
COMMENT ON COLUMN sc_file_item_match.material_handling IS '主材处理方式：INCLUDED_BY_QUOTA、ADD_AS_CONSUMPTION、MANUAL_CONFIRM';
COMMENT ON COLUMN sc_file_item_match.match_remark IS '简短匹配原因或处理说明，不保存大模型长文本';
COMMENT ON COLUMN sc_file_item_match.create_user_id IS '创建人';
COMMENT ON COLUMN sc_file_item_match.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_file_item_match.create_date IS '创建时间';

-- 定额匹配结果关联关系表
CREATE TABLE IF NOT EXISTS sc_file_item_match_relation (
    id varchar(36) NOT NULL,
    source_match_id varchar(36) NOT NULL,
    associated_match_id varchar(36) NOT NULL,
    CONSTRAINT pk_sc_file_item_match_relation PRIMARY KEY (id),
    CONSTRAINT uq_sc_match_relation_pair UNIQUE (source_match_id, associated_match_id)
);
COMMENT ON TABLE sc_file_item_match_relation IS '主定额与关联定额匹配结果关系表';
COMMENT ON COLUMN sc_file_item_match_relation.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_file_item_match_relation.source_match_id IS '来源主定额匹配结果 UUID，关联 sc_file_item_match.id';
COMMENT ON COLUMN sc_file_item_match_relation.associated_match_id IS '关联定额匹配结果 UUID，关联 sc_file_item_match.id';

-- A-06 定额关联规则主表：规则名称与所属定额库
CREATE TABLE IF NOT EXISTS sc_rule_a06 (
    id varchar(36) NOT NULL,
    name varchar(200),
    de_library_id varchar(36),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_rule_a06 PRIMARY KEY (id)
);
COMMENT ON TABLE sc_rule_a06 IS 'A-06 定额关联规则主表：规则名称与所属定额库';
COMMENT ON COLUMN sc_rule_a06.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_rule_a06.name IS '规则名称';
COMMENT ON COLUMN sc_rule_a06.de_library_id IS '定额库 UUID，关联 sc_de_library.id';

-- A-06 规则明细表：以编号区间描述主/关联定额范围（is_main=1 主定额范围、0 关联定额范围，
-- 均直接挂在规则下，换算比例 = 关联工作量 / 主定额工作量）
CREATE TABLE IF NOT EXISTS sc_rule_a06_de_item (
    id varchar(36) NOT NULL,
    rule_id varchar(36) NOT NULL,
    start_code varchar(50) NOT NULL,
    end_code varchar(50) NOT NULL,
    is_main varchar(1) NOT NULL DEFAULT '1',
    quantity varchar(200),
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_rule_a06_de_item PRIMARY KEY (id)
);
COMMENT ON TABLE sc_rule_a06_de_item IS 'A-06 规则明细：主/关联定额的编号区间及工作量、关联信息';
COMMENT ON COLUMN sc_rule_a06_de_item.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_rule_a06_de_item.rule_id IS '规则 UUID，关联 sc_rule_a06.id';
COMMENT ON COLUMN sc_rule_a06_de_item.start_code IS '起始定额编号（含边界）';
COMMENT ON COLUMN sc_rule_a06_de_item.end_code IS '结束定额编号（含边界）';
COMMENT ON COLUMN sc_rule_a06_de_item.is_main IS '是否主定额：1 主定额范围、0 关联定额范围';
COMMENT ON COLUMN sc_rule_a06_de_item.quantity IS '工作量（该区间内定额统一值）';
COMMENT ON COLUMN sc_rule_a06_de_item.remark IS '关联信息说明';

-- 匹配定额消耗明细表
CREATE TABLE IF NOT EXISTS sc_file_item_match_consume (
    id varchar(36) NOT NULL,
    match_id varchar(36),
    source_de_consume_id varchar(36),
    source_file_item_id varchar(36),
    code varchar(100),
    name varchar(500),
    type varchar(32),
    unit varchar(50),
    formula varchar(2000),
    quantity numeric(18,6),
    original_price numeric(18,6),
    price numeric(18,6),
    price_match_status varchar(32),
    price_match_method varchar(32),
    price_match_score numeric(8,6),
    price_match_remark varchar(500),
    sort_no integer,
    remark varchar(1000),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_file_item_match_consume PRIMARY KEY (id),
    CONSTRAINT ck_sc_match_consume_source CHECK ((source_de_consume_id IS NULL) <> (source_file_item_id IS NULL))
);
COMMENT ON TABLE sc_file_item_match_consume IS '匹配定额消耗明细表';
COMMENT ON COLUMN sc_file_item_match_consume.id IS 'Java 生成 UUID，消耗明细主键';
COMMENT ON COLUMN sc_file_item_match_consume.match_id IS '所属匹配结果 UUID，关联 sc_file_item_match.id';
COMMENT ON COLUMN sc_file_item_match_consume.source_de_consume_id IS '来源基础定额消耗 UUID，关联 sc_de_consume.id；基础消耗来源时填写';
COMMENT ON COLUMN sc_file_item_match_consume.source_file_item_id IS '来源原始工程量项 UUID，关联 sc_file_item.id；追加主材/设备时填写';
COMMENT ON COLUMN sc_file_item_match_consume.code IS '消耗编号快照';
COMMENT ON COLUMN sc_file_item_match_consume.name IS '消耗名称快照，不允许直接改名';
COMMENT ON COLUMN sc_file_item_match_consume.type IS '消耗类型字典编码：LABOR、MATERIAL、MACHINE、EQUIPMENT';
COMMENT ON COLUMN sc_file_item_match_consume.unit IS '消耗单位';
COMMENT ON COLUMN sc_file_item_match_consume.formula IS '消耗工程量计算式，可人工修改';
COMMENT ON COLUMN sc_file_item_match_consume.quantity IS '消耗工程量，可人工修改';
COMMENT ON COLUMN sc_file_item_match_consume.original_price IS '初始单价快照';
COMMENT ON COLUMN sc_file_item_match_consume.price IS '当前使用单价，可在价格匹配/人工调整后修改';
COMMENT ON COLUMN sc_file_item_match_consume.price_match_status IS '价格匹配状态字典编码';
COMMENT ON COLUMN sc_file_item_match_consume.price_match_method IS '价格匹配方式字典编码';
COMMENT ON COLUMN sc_file_item_match_consume.price_match_score IS '价格匹配得分，可为空';
COMMENT ON COLUMN sc_file_item_match_consume.price_match_remark IS '价格匹配简短说明';
COMMENT ON COLUMN sc_file_item_match_consume.sort_no IS '同一匹配结果下的显示顺序';
COMMENT ON COLUMN sc_file_item_match_consume.remark IS '消耗备注';
COMMENT ON COLUMN sc_file_item_match_consume.create_user_id IS '创建人';
COMMENT ON COLUMN sc_file_item_match_consume.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_file_item_match_consume.create_date IS '创建时间';

-- 历史案例项目表
CREATE TABLE IF NOT EXISTS sc_history_project (
    id varchar(36) NOT NULL,
    code varchar(64),
    name varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_history_project PRIMARY KEY (id)
);
COMMENT ON TABLE sc_history_project IS '历史案例项目表';
COMMENT ON COLUMN sc_history_project.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_history_project.code IS '造价文件中的项目编号';
COMMENT ON COLUMN sc_history_project.name IS '项目名称';
COMMENT ON COLUMN sc_history_project.create_user_id IS '案例创建人';
COMMENT ON COLUMN sc_history_project.create_org_id IS '创建人所属机构';
COMMENT ON COLUMN sc_history_project.create_date IS '案例创建时间';

-- 历史案例 CBS 快照表
CREATE TABLE IF NOT EXISTS sc_history_project_cbs (
    id varchar(36) NOT NULL,
    history_project_id varchar(36),
    parent_id varchar(36),
    sort_no integer,
    code varchar(100),
    name varchar(500),
    status varchar(32),
    price_basis_name varchar(500),
    de_library_name varchar(500),
    qf_model_name varchar(500),
    CONSTRAINT pk_sc_history_project_cbs PRIMARY KEY (id)
);
COMMENT ON TABLE sc_history_project_cbs IS '历史案例 CBS 快照表';
COMMENT ON COLUMN sc_history_project_cbs.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_history_project_cbs.history_project_id IS '所属历史案例，关联 sc_history_project.id';
COMMENT ON COLUMN sc_history_project_cbs.parent_id IS '父 CBS 节点 UUID；案例根节点为空';
COMMENT ON COLUMN sc_history_project_cbs.sort_no IS '同级排序号';
COMMENT ON COLUMN sc_history_project_cbs.code IS '造价文件中的 CBS 编号';
COMMENT ON COLUMN sc_history_project_cbs.name IS 'CBS 名称';
COMMENT ON COLUMN sc_history_project_cbs.status IS 'CBS 状态字典编码快照';
COMMENT ON COLUMN sc_history_project_cbs.price_basis_name IS '计价依据名称快照';
COMMENT ON COLUMN sc_history_project_cbs.de_library_name IS '定额库名称快照';
COMMENT ON COLUMN sc_history_project_cbs.qf_model_name IS '取费模板名称快照';

-- 历史案例成果项表
CREATE TABLE IF NOT EXISTS sc_history_project_item (
    id varchar(36) NOT NULL,
    history_project_cbs_id varchar(36),
    parent_id varchar(36),
    sort_no integer,
    type varchar(32),
    code varchar(100),
    name varchar(1000),
    unit varchar(50),
    formula varchar(2000),
    quantity numeric(18,6),
    price numeric(18,6),
    amount numeric(18,6),
    base_price numeric(18,6),
    cl_fee numeric(18,6),
    rg_fee numeric(18,6),
    jx_fee numeric(18,6),
    zc_fee numeric(18,6),
    sb_fee numeric(18,6),
    remark varchar(1000),
    CONSTRAINT pk_sc_history_project_item PRIMARY KEY (id)
);
COMMENT ON TABLE sc_history_project_item IS '历史案例成果项表';
COMMENT ON COLUMN sc_history_project_item.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_history_project_item.history_project_cbs_id IS '所属案例 CBS 节点，关联 sc_history_project_cbs.id';
COMMENT ON COLUMN sc_history_project_item.parent_id IS '父成果项 UUID；CBS 下的首层成果项为空';
COMMENT ON COLUMN sc_history_project_item.sort_no IS '同级排序号';
COMMENT ON COLUMN sc_history_project_item.type IS '节点类型字典编码：SUBSECTION、QUOTA、INDICATOR、EQUIPMENT、MATERIAL';
COMMENT ON COLUMN sc_history_project_item.code IS '造价文件中的编号';
COMMENT ON COLUMN sc_history_project_item.name IS '节点名称';
COMMENT ON COLUMN sc_history_project_item.unit IS '单位';
COMMENT ON COLUMN sc_history_project_item.formula IS '工程量计算式';
COMMENT ON COLUMN sc_history_project_item.quantity IS '工程量';
COMMENT ON COLUMN sc_history_project_item.price IS '单价';
COMMENT ON COLUMN sc_history_project_item.amount IS '合价或金额';
COMMENT ON COLUMN sc_history_project_item.base_price IS '定额基价';
COMMENT ON COLUMN sc_history_project_item.cl_fee IS '材料费';
COMMENT ON COLUMN sc_history_project_item.rg_fee IS '人工费';
COMMENT ON COLUMN sc_history_project_item.jx_fee IS '机械费';
COMMENT ON COLUMN sc_history_project_item.zc_fee IS '主材费';
COMMENT ON COLUMN sc_history_project_item.sb_fee IS '设备费';
COMMENT ON COLUMN sc_history_project_item.remark IS '备注';

-- 历史案例定额消耗快照表
CREATE TABLE IF NOT EXISTS sc_history_project_consume (
    id varchar(36) NOT NULL,
    history_project_item_id varchar(36),
    sort_no integer,
    code varchar(100),
    name varchar(500),
    type varchar(32),
    unit varchar(50),
    formula varchar(2000),
    quantity numeric(18,6),
    price numeric(18,6),
    amount numeric(18,6),
    remark varchar(1000),
    CONSTRAINT pk_sc_history_project_consume PRIMARY KEY (id)
);
COMMENT ON TABLE sc_history_project_consume IS '历史案例定额消耗快照表';
COMMENT ON COLUMN sc_history_project_consume.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_history_project_consume.history_project_item_id IS '所属定额/指标成果项，关联 sc_history_project_item.id';
COMMENT ON COLUMN sc_history_project_consume.sort_no IS '消耗项显示顺序';
COMMENT ON COLUMN sc_history_project_consume.code IS '消耗编号';
COMMENT ON COLUMN sc_history_project_consume.name IS '消耗名称';
COMMENT ON COLUMN sc_history_project_consume.type IS '消耗类型字典编码：LABOR、MATERIAL、MACHINE、EQUIPMENT';
COMMENT ON COLUMN sc_history_project_consume.unit IS '消耗单位';
COMMENT ON COLUMN sc_history_project_consume.formula IS '消耗工程量计算式';
COMMENT ON COLUMN sc_history_project_consume.quantity IS '消耗数量';
COMMENT ON COLUMN sc_history_project_consume.price IS '消耗单价';
COMMENT ON COLUMN sc_history_project_consume.amount IS '消耗合价或金额';
COMMENT ON COLUMN sc_history_project_consume.remark IS '备注';

-- 定额匹配经验表
CREATE TABLE IF NOT EXISTS sc_match_experience (
    id varchar(36) NOT NULL,
    project_id varchar(36),
    project_code varchar(64),
    project_name varchar(200),
    single_project_cbs_id varchar(36),
    single_project_name varchar(200),
    unit_project_cbs_id varchar(36),
    unit_project_name varchar(200),
    source_type varchar(32),
    source_name varchar(500),
    source_specification varchar(2000),
    source_unit varchar(50),
    de_library_id varchar(36),
    de_item_id varchar(36),
    de_code varchar(100),
    de_name varchar(500),
    de_unit varchar(50),
    de_price numeric(18,6),
    remark varchar(1000),
    status varchar(32),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_match_experience PRIMARY KEY (id)
);
COMMENT ON TABLE sc_match_experience IS '定额匹配经验表';
COMMENT ON COLUMN sc_match_experience.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_match_experience.project_id IS '来源项目 UUID，用于追溯，不设置级联删除';
COMMENT ON COLUMN sc_match_experience.project_code IS '来源项目编号快照';
COMMENT ON COLUMN sc_match_experience.project_name IS '来源项目名称快照';
COMMENT ON COLUMN sc_match_experience.single_project_cbs_id IS '来源单项工程 CBS 节点 UUID';
COMMENT ON COLUMN sc_match_experience.single_project_name IS '单项工程名称快照';
COMMENT ON COLUMN sc_match_experience.unit_project_cbs_id IS '来源单位工程 CBS 节点 UUID';
COMMENT ON COLUMN sc_match_experience.unit_project_name IS '单位工程名称快照';
COMMENT ON COLUMN sc_match_experience.source_type IS '来源项类型字典编码：EQUIPMENT、MATERIAL';
COMMENT ON COLUMN sc_match_experience.source_name IS '设备/主材名称快照';
COMMENT ON COLUMN sc_match_experience.source_specification IS '设备/主材规格快照';
COMMENT ON COLUMN sc_match_experience.source_unit IS '设备/主材单位快照';
COMMENT ON COLUMN sc_match_experience.de_library_id IS '定额/指标库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_match_experience.de_item_id IS '匹配的定额/指标 UUID，关联 sc_de_item.id';
COMMENT ON COLUMN sc_match_experience.de_code IS '定额/指标编号快照';
COMMENT ON COLUMN sc_match_experience.de_name IS '定额/指标名称快照';
COMMENT ON COLUMN sc_match_experience.de_unit IS '定额/指标单位快照';
COMMENT ON COLUMN sc_match_experience.de_price IS '定额基价快照';
COMMENT ON COLUMN sc_match_experience.remark IS '经验口径说明；批量保存时每条记录重复保存';
COMMENT ON COLUMN sc_match_experience.status IS '经验状态字典编码，如 PENDING_REVIEW、PUBLISHED、RETURNED、DISABLED';
COMMENT ON COLUMN sc_match_experience.create_user_id IS '经验贡献人';
COMMENT ON COLUMN sc_match_experience.create_org_id IS '贡献人所属机构';
COMMENT ON COLUMN sc_match_experience.create_date IS '创建时间';

-- 当前流程任务表
CREATE TABLE IF NOT EXISTS sc_task (
    id varchar(36) NOT NULL,
    master_id varchar(36),
    name varchar(200),
    task_type varchar(32),
    state varchar(32),
    refer_user_id varchar(36),
    refer_org_id varchar(36),
    refer_date varchar(19),
    refer_idea varchar(1000),
    audit_user_id varchar(36),
    audit_org_id varchar(36),
    audit_date varchar(19),
    audit_idea varchar(1000),
    remark varchar(500),
    CONSTRAINT pk_sc_task PRIMARY KEY (id)
);
COMMENT ON TABLE sc_task IS '当前流程任务表';
COMMENT ON COLUMN sc_task.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_task.master_id IS '业务数据 UUID，由 task_type 确定对应业务表';
COMMENT ON COLUMN sc_task.name IS '任务名称';
COMMENT ON COLUMN sc_task.task_type IS '流程类型字典编码，如经验审核';
COMMENT ON COLUMN sc_task.state IS '当前任务状态字典编码，如 PENDING、COMPLETED、RETURNED';
COMMENT ON COLUMN sc_task.refer_user_id IS '提交人';
COMMENT ON COLUMN sc_task.refer_org_id IS '提交人所属机构';
COMMENT ON COLUMN sc_task.refer_date IS '提交时间';
COMMENT ON COLUMN sc_task.refer_idea IS '提交说明';
COMMENT ON COLUMN sc_task.audit_user_id IS '当前或最后审核人，可空';
COMMENT ON COLUMN sc_task.audit_org_id IS '审核人所属机构，可空';
COMMENT ON COLUMN sc_task.audit_date IS '审核时间，可空';
COMMENT ON COLUMN sc_task.audit_idea IS '审核意见，可空';
COMMENT ON COLUMN sc_task.remark IS '备注';

-- 流程流转记录表
CREATE TABLE IF NOT EXISTS sc_flow_log (
    id varchar(36) NOT NULL,
    master_id varchar(36),
    task_type varchar(32),
    state varchar(32),
    refer_user_id varchar(36),
    refer_org_id varchar(36),
    refer_date varchar(19),
    audit_user_id varchar(36),
    audit_org_id varchar(36),
    audit_date varchar(19),
    audit_idea varchar(1000),
    remark varchar(1000),
    CONSTRAINT pk_sc_flow_log PRIMARY KEY (id)
);
COMMENT ON TABLE sc_flow_log IS '流程流转记录表';
COMMENT ON COLUMN sc_flow_log.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_flow_log.master_id IS '业务数据 UUID';
COMMENT ON COLUMN sc_flow_log.task_type IS '流程类型字典编码';
COMMENT ON COLUMN sc_flow_log.state IS '本次流转结果字典编码，如 SUBMITTED、APPROVED、RETURNED';
COMMENT ON COLUMN sc_flow_log.refer_user_id IS '本次提交人，可空';
COMMENT ON COLUMN sc_flow_log.refer_org_id IS '提交人所属机构，可空';
COMMENT ON COLUMN sc_flow_log.refer_date IS '提交时间，可空';
COMMENT ON COLUMN sc_flow_log.audit_user_id IS '本次审核人，可空';
COMMENT ON COLUMN sc_flow_log.audit_org_id IS '审核人所属机构，可空';
COMMENT ON COLUMN sc_flow_log.audit_date IS '审核时间，可空';
COMMENT ON COLUMN sc_flow_log.audit_idea IS '审核意见，可空';
COMMENT ON COLUMN sc_flow_log.remark IS '本次流转说明';

-- 平台 CBS 模板主表
CREATE TABLE IF NOT EXISTS sc_cbs (
    id varchar(36) NOT NULL,
    code varchar(64),
    name varchar(200),
    specialty_code varchar(32),
    version_no integer,
    status varchar(32),
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_cbs PRIMARY KEY (id)
);
COMMENT ON TABLE sc_cbs IS '平台 CBS 模板主表';
COMMENT ON COLUMN sc_cbs.id IS 'Java 生成 UUID，模板主键';
COMMENT ON COLUMN sc_cbs.code IS 'CBS 模板编码';
COMMENT ON COLUMN sc_cbs.name IS 'CBS 模板名称';
COMMENT ON COLUMN sc_cbs.specialty_code IS '所属专业字典编码';
COMMENT ON COLUMN sc_cbs.version_no IS '模板版本号';
COMMENT ON COLUMN sc_cbs.status IS '模板状态字典编码';
COMMENT ON COLUMN sc_cbs.remark IS '备注';
COMMENT ON COLUMN sc_cbs.create_user_id IS '创建人';
COMMENT ON COLUMN sc_cbs.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_cbs.create_date IS '创建时间';

-- 平台 CBS 模板明细表
CREATE TABLE IF NOT EXISTS sc_cbs_detail (
    id varchar(36) NOT NULL,
    cbs_id varchar(36),
    parent_id varchar(36),
    code varchar(64),
    name varchar(200),
    category_code varchar(32),
    category_name varchar(100),
    sort_no integer,
    inner_code varchar(500),
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_cbs_detail PRIMARY KEY (id)
);
COMMENT ON TABLE sc_cbs_detail IS '平台 CBS 模板明细表';
COMMENT ON COLUMN sc_cbs_detail.id IS 'Java 生成 UUID，明细主键';
COMMENT ON COLUMN sc_cbs_detail.cbs_id IS '所属 CBS 模板 UUID，关联 sc_cbs.id';
COMMENT ON COLUMN sc_cbs_detail.parent_id IS '父节点 UUID，模板根节点为空';
COMMENT ON COLUMN sc_cbs_detail.code IS 'CBS 明细编码';
COMMENT ON COLUMN sc_cbs_detail.name IS 'CBS 明细名称';
COMMENT ON COLUMN sc_cbs_detail.category_code IS '分类字典编码';
COMMENT ON COLUMN sc_cbs_detail.category_name IS '分类名称快照';
COMMENT ON COLUMN sc_cbs_detail.sort_no IS '同级排序号';
COMMENT ON COLUMN sc_cbs_detail.inner_code IS '层级路径码';
COMMENT ON COLUMN sc_cbs_detail.remark IS '备注';
COMMENT ON COLUMN sc_cbs_detail.create_user_id IS '创建人';
COMMENT ON COLUMN sc_cbs_detail.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_cbs_detail.create_date IS '创建时间';

-- 项目 CBS 表
CREATE TABLE IF NOT EXISTS sc_project_cbs (
    id varchar(36) NOT NULL,
    project_id varchar(36),
    parent_id varchar(36),
    code varchar(64),
    name varchar(200),
    source_detail_name varchar(200),
    category_code varchar(32),
    category_name varchar(100),
    sort_no integer,
    inner_code varchar(500),
    source_cbs_id varchar(36),
    source_cbs_detail_id varchar(36),
    source_version_no integer,
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_project_cbs PRIMARY KEY (id)
);
COMMENT ON TABLE sc_project_cbs IS '项目 CBS 表';
COMMENT ON COLUMN sc_project_cbs.id IS 'Java 生成 UUID，项目 CBS 节点主键';
COMMENT ON COLUMN sc_project_cbs.project_id IS '所属项目 UUID，关联 sc_project.id';
COMMENT ON COLUMN sc_project_cbs.parent_id IS '父节点 UUID，项目根节点为空';
COMMENT ON COLUMN sc_project_cbs.code IS '项目 CBS 编码，自建节点可为空';
COMMENT ON COLUMN sc_project_cbs.name IS '项目显示名称';
COMMENT ON COLUMN sc_project_cbs.source_detail_name IS '标准节点原始名称快照';
COMMENT ON COLUMN sc_project_cbs.category_code IS '分类字典编码';
COMMENT ON COLUMN sc_project_cbs.category_name IS '分类名称快照';
COMMENT ON COLUMN sc_project_cbs.sort_no IS '同级排序号';
COMMENT ON COLUMN sc_project_cbs.inner_code IS '项目层级路径码';
COMMENT ON COLUMN sc_project_cbs.source_cbs_id IS '来源 CBS 模板 UUID，自建节点为空';
COMMENT ON COLUMN sc_project_cbs.source_cbs_detail_id IS '来源标准 CBS 明细 UUID，自建节点为空';
COMMENT ON COLUMN sc_project_cbs.source_version_no IS '来源 CBS 模板版本号，自建节点为空';
COMMENT ON COLUMN sc_project_cbs.remark IS '备注';
COMMENT ON COLUMN sc_project_cbs.create_user_id IS '创建人';
COMMENT ON COLUMN sc_project_cbs.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_project_cbs.create_date IS '创建时间';

-- 计价依据表
CREATE TABLE IF NOT EXISTS sc_price_basis (
    id varchar(36) NOT NULL,
    code varchar(64),
    name varchar(200),
    specialty_code varchar(32),
    remark varchar(500),
    CONSTRAINT pk_sc_price_basis PRIMARY KEY (id)
);
COMMENT ON TABLE sc_price_basis IS '计价依据表';
COMMENT ON COLUMN sc_price_basis.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_price_basis.code IS '计价依据编码';
COMMENT ON COLUMN sc_price_basis.name IS '计价依据名称';
COMMENT ON COLUMN sc_price_basis.specialty_code IS '所属专业字典编码';
COMMENT ON COLUMN sc_price_basis.remark IS '备注';

-- 定额库表
CREATE TABLE IF NOT EXISTS sc_de_library (
    id varchar(36) NOT NULL,
    price_basis_id varchar(36),
    code varchar(64),
    name varchar(200),
    type varchar(32),
    specialty_code varchar(32),
    remark varchar(500),
    CONSTRAINT pk_sc_de_library PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_library IS '定额库表';
COMMENT ON COLUMN sc_de_library.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_library.price_basis_id IS '所属计价依据 UUID，关联 sc_price_basis.id';
COMMENT ON COLUMN sc_de_library.code IS '定额库编码';
COMMENT ON COLUMN sc_de_library.name IS '定额库名称';
COMMENT ON COLUMN sc_de_library.type IS '类型字典编码：QUOTA、INDICATOR';
COMMENT ON COLUMN sc_de_library.specialty_code IS '所属专业字典编码';
COMMENT ON COLUMN sc_de_library.remark IS '备注';

-- 定额目录表
CREATE TABLE IF NOT EXISTS sc_de_directory (
    id varchar(36) NOT NULL,
    de_library_id varchar(36),
    type varchar(32),
    bsid varchar(100),
    parent_id varchar(36),
    name varchar(200),
    description text,
    sort_no integer,
    CONSTRAINT pk_sc_de_directory PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_directory IS '定额目录表';
COMMENT ON COLUMN sc_de_directory.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_directory.de_library_id IS '所属定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_de_directory.type IS '类型字典编码：QUOTA、INDICATOR';
COMMENT ON COLUMN sc_de_directory.bsid IS '软件原始目录层级编号，如 1.1.1.3';
COMMENT ON COLUMN sc_de_directory.parent_id IS '父目录 UUID，根目录为空';
COMMENT ON COLUMN sc_de_directory.name IS '目录名称';
COMMENT ON COLUMN sc_de_directory.description IS '目录说明';
COMMENT ON COLUMN sc_de_directory.sort_no IS '同级排序号';

-- 定额/指标基础数据表
CREATE TABLE IF NOT EXISTS sc_de_item (
    id varchar(36) NOT NULL,
    de_library_id varchar(36),
    directory_id varchar(36),
    type varchar(32),
    code varchar(100),
    name varchar(500),
    description text,
    unit varchar(50),
    base_price numeric(18,6),
    cl_fee numeric(18,6),
    rg_fee numeric(18,6),
    jx_fee numeric(18,6),
    CONSTRAINT pk_sc_de_item PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_item IS '定额/指标基础数据表';
COMMENT ON COLUMN sc_de_item.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_item.de_library_id IS '所属定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_de_item.directory_id IS '所属定额目录 UUID，关联 sc_de_directory.id';
COMMENT ON COLUMN sc_de_item.type IS '类型字典编码：QUOTA、INDICATOR';
COMMENT ON COLUMN sc_de_item.code IS '定额或指标编号';
COMMENT ON COLUMN sc_de_item.name IS '定额或指标名称';
COMMENT ON COLUMN sc_de_item.description IS '定额说明、工作内容、适用范围';
COMMENT ON COLUMN sc_de_item.unit IS '计量单位';
COMMENT ON COLUMN sc_de_item.base_price IS '基价，对应外部软件 BasePrice';
COMMENT ON COLUMN sc_de_item.cl_fee IS '材料费，对应外部软件 CLFee';
COMMENT ON COLUMN sc_de_item.rg_fee IS '人工费，对应外部软件 RGFee';
COMMENT ON COLUMN sc_de_item.jx_fee IS '机械费，对应外部软件 JXFee';

-- 人材机目录树表
CREATE TABLE IF NOT EXISTS sc_de_rcj_category (
    id varchar(36) NOT NULL,
    de_library_id varchar(36),
    name varchar(200),
    gljtype varchar(32),
    bsid varchar(100),
    parentid varchar(36),
    orderno integer,
    CONSTRAINT pk_sc_de_rcj_category PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_rcj_category IS '人材机目录树表';
COMMENT ON COLUMN sc_de_rcj_category.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_rcj_category.de_library_id IS '所属定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_de_rcj_category.name IS '目录名称';
COMMENT ON COLUMN sc_de_rcj_category.gljtype IS '人材机类别';
COMMENT ON COLUMN sc_de_rcj_category.bsid IS '软件原始目录层级编号';
COMMENT ON COLUMN sc_de_rcj_category.parentid IS '父目录 UUID，根目录为空';
COMMENT ON COLUMN sc_de_rcj_category.orderno IS '同级排序号';

-- 人材机基础数据表
CREATE TABLE IF NOT EXISTS sc_de_rcj (
    id varchar(36) NOT NULL,
    de_library_id varchar(36),
    categoryid varchar(36),
    code varchar(100),
    name varchar(500),
    type varchar(32),
    unit varchar(50),
    price numeric(18,6),
    remark varchar(500),
    CONSTRAINT pk_sc_de_rcj PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_rcj IS '人材机基础数据表';
COMMENT ON COLUMN sc_de_rcj.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_rcj.de_library_id IS '所属定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_de_rcj.categoryid IS '所属人材机目录 UUID，关联 sc_de_rcj_category.id';
COMMENT ON COLUMN sc_de_rcj.code IS '人材机编号';
COMMENT ON COLUMN sc_de_rcj.name IS '人材机名称';
COMMENT ON COLUMN sc_de_rcj.type IS '人材机类型字典编码：LABOR、MATERIAL、MACHINE';
COMMENT ON COLUMN sc_de_rcj.unit IS '计量单位';
COMMENT ON COLUMN sc_de_rcj.price IS '人材机单价';
COMMENT ON COLUMN sc_de_rcj.remark IS '备注';

-- 定额消耗表
CREATE TABLE IF NOT EXISTS sc_de_consume (
    id varchar(36) NOT NULL,
    de_item_id varchar(36),
    rcj_id varchar(36),
    code varchar(100),
    name varchar(500),
    type varchar(32),
    unit varchar(50),
    price numeric(18,6),
    quantity numeric(18,6),
    sort_no integer,
    remark varchar(500),
    CONSTRAINT pk_sc_de_consume PRIMARY KEY (id)
);
COMMENT ON TABLE sc_de_consume IS '定额消耗表';
COMMENT ON COLUMN sc_de_consume.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_de_consume.de_item_id IS '定额或指标ID，关联 sc_de_item.id';
COMMENT ON COLUMN sc_de_consume.rcj_id IS '人材机ID，关联 sc_de_rcj.id';
COMMENT ON COLUMN sc_de_consume.code IS '人材机编号快照';
COMMENT ON COLUMN sc_de_consume.name IS '人材机名称快照';
COMMENT ON COLUMN sc_de_consume.type IS '人材机类型快照';
COMMENT ON COLUMN sc_de_consume.unit IS '计量单位快照';
COMMENT ON COLUMN sc_de_consume.price IS '单价快照';
COMMENT ON COLUMN sc_de_consume.quantity IS '定额消耗数量';
COMMENT ON COLUMN sc_de_consume.sort_no IS '定额消耗组成顺序';
COMMENT ON COLUMN sc_de_consume.remark IS '备注';

-- 价格库表
CREATE TABLE IF NOT EXISTS sc_price (
    id varchar(36) NOT NULL,
    code varchar(100),
    description varchar(1000),
    specification varchar(500),
    unit varchar(50),
    excl_tax_unit_price numeric(18,6),
    price_source varchar(1000),
    source_excel_name varchar(255),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_price PRIMARY KEY (id)
);
COMMENT ON TABLE sc_price IS '价格库表';
COMMENT ON COLUMN sc_price.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_price.code IS '物料编码';
COMMENT ON COLUMN sc_price.description IS '物料描述';
COMMENT ON COLUMN sc_price.specification IS '规格';
COMMENT ON COLUMN sc_price.unit IS '单位';
COMMENT ON COLUMN sc_price.excl_tax_unit_price IS '不含税单价';
COMMENT ON COLUMN sc_price.price_source IS '价格来源说明';
COMMENT ON COLUMN sc_price.source_excel_name IS '导入该价格记录的 Excel 文件名';
COMMENT ON COLUMN sc_price.create_user_id IS '录入或导入人员';
COMMENT ON COLUMN sc_price.create_org_id IS '录入或导入人员所属机构';
COMMENT ON COLUMN sc_price.create_date IS '录入或导入时间';

-- 项目 CBS-定额库关联表
CREATE TABLE IF NOT EXISTS sc_project_cbs_de_library (
    id varchar(36) NOT NULL,
    project_id varchar(36),
    project_cbs_id varchar(36),
    de_library_id varchar(36),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_project_cbs_de_library PRIMARY KEY (id)
);
COMMENT ON TABLE sc_project_cbs_de_library IS '项目 CBS-定额库关联表';
COMMENT ON COLUMN sc_project_cbs_de_library.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_project_cbs_de_library.project_id IS '所属项目 UUID，关联 sc_project.id';
COMMENT ON COLUMN sc_project_cbs_de_library.project_cbs_id IS '当前项目 CBS 节点 UUID，关联 sc_project_cbs.id';
COMMENT ON COLUMN sc_project_cbs_de_library.de_library_id IS '定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_project_cbs_de_library.create_user_id IS '创建人';
COMMENT ON COLUMN sc_project_cbs_de_library.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_project_cbs_de_library.create_date IS '创建时间';

-- 平台内置取费模板主表
CREATE TABLE IF NOT EXISTS sc_qf_model (
    id varchar(36) NOT NULL,
    de_library_id varchar(36),
    code varchar(64),
    name varchar(200),
    remark varchar(500),
    CONSTRAINT pk_sc_qf_model PRIMARY KEY (id)
);
COMMENT ON TABLE sc_qf_model IS '平台内置取费模板主表';
COMMENT ON COLUMN sc_qf_model.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_qf_model.de_library_id IS '所属定额库 UUID，关联 sc_de_library.id';
COMMENT ON COLUMN sc_qf_model.code IS '取费模板编码';
COMMENT ON COLUMN sc_qf_model.name IS '取费模板名称';
COMMENT ON COLUMN sc_qf_model.remark IS '备注';

-- 平台内置取费模板参数定义表
CREATE TABLE IF NOT EXISTS sc_qf_model_param (
    id varchar(36) NOT NULL,
    qf_model_id varchar(36),
    param_key varchar(64),
    param_name varchar(200),
    param_type varchar(32),
    default_value text,
    param_options text,
    section_code varchar(64),
    section_name varchar(200),
    section_sort integer,
    sort_no integer,
    required_flag smallint,
    remark varchar(500),
    CONSTRAINT pk_sc_qf_model_param PRIMARY KEY (id),
    CONSTRAINT ck_sc_qf_model_param_required_flag CHECK (required_flag IS NULL OR required_flag IN (0, 1))
);
COMMENT ON TABLE sc_qf_model_param IS '平台内置取费模板参数定义表';
COMMENT ON COLUMN sc_qf_model_param.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_qf_model_param.qf_model_id IS '所属取费模板 UUID，关联 sc_qf_model.id';
COMMENT ON COLUMN sc_qf_model_param.param_key IS '参数编码，同时作为软件参数编码';
COMMENT ON COLUMN sc_qf_model_param.param_name IS '参数名称';
COMMENT ON COLUMN sc_qf_model_param.param_type IS '参数类型字典编码';
COMMENT ON COLUMN sc_qf_model_param.default_value IS '默认值';
COMMENT ON COLUMN sc_qf_model_param.param_options IS '可选项，使用 JSON 字符串保存，不使用 PostgreSQL 专用 jsonb';
COMMENT ON COLUMN sc_qf_model_param.section_code IS '参数分组编码';
COMMENT ON COLUMN sc_qf_model_param.section_name IS '参数分组名称';
COMMENT ON COLUMN sc_qf_model_param.section_sort IS '参数分组显示顺序';
COMMENT ON COLUMN sc_qf_model_param.sort_no IS '分组内参数显示顺序';
COMMENT ON COLUMN sc_qf_model_param.required_flag IS '是否必填';
COMMENT ON COLUMN sc_qf_model_param.remark IS '备注';

-- 项目取费模板快照表
CREATE TABLE IF NOT EXISTS sc_project_qf_model (
    id varchar(36) NOT NULL,
    project_cbs_de_library_id varchar(36),
    source_qf_model_id varchar(36),
    code varchar(64),
    name varchar(200),
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_project_qf_model PRIMARY KEY (id)
);
COMMENT ON TABLE sc_project_qf_model IS '项目取费模板快照表';
COMMENT ON COLUMN sc_project_qf_model.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_project_qf_model.project_cbs_de_library_id IS '项目 CBS-定额库关联 UUID';
COMMENT ON COLUMN sc_project_qf_model.source_qf_model_id IS '来源内置模板 UUID，关联 sc_qf_model.id';
COMMENT ON COLUMN sc_project_qf_model.code IS '模板编码快照';
COMMENT ON COLUMN sc_project_qf_model.name IS '模板名称快照';
COMMENT ON COLUMN sc_project_qf_model.remark IS '备注';
COMMENT ON COLUMN sc_project_qf_model.create_user_id IS '创建人';
COMMENT ON COLUMN sc_project_qf_model.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_project_qf_model.create_date IS '创建时间';

-- 项目取费模板参数快照表
CREATE TABLE IF NOT EXISTS sc_project_qf_model_param (
    id varchar(36) NOT NULL,
    project_qf_model_id varchar(36),
    source_param_id varchar(36),
    param_key varchar(64),
    param_name varchar(200),
    param_type varchar(32),
    param_options text,
    param_value text,
    section_code varchar(64),
    section_name varchar(200),
    section_sort integer,
    sort_no integer,
    required_flag smallint,
    remark varchar(500),
    create_user_id varchar(36),
    create_org_id varchar(36),
    create_date varchar(19),
    CONSTRAINT pk_sc_project_qf_model_param PRIMARY KEY (id),
    CONSTRAINT ck_sc_project_qf_model_param_required_flag CHECK (required_flag IS NULL OR required_flag IN (0, 1))
);
COMMENT ON TABLE sc_project_qf_model_param IS '项目取费模板参数快照表';
COMMENT ON COLUMN sc_project_qf_model_param.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sc_project_qf_model_param.project_qf_model_id IS '项目取费模板 UUID';
COMMENT ON COLUMN sc_project_qf_model_param.source_param_id IS '来源内置参数 UUID，关联 sc_qf_model_param.id';
COMMENT ON COLUMN sc_project_qf_model_param.param_key IS '参数编码，同时作为软件参数编码';
COMMENT ON COLUMN sc_project_qf_model_param.param_name IS '参数名称快照';
COMMENT ON COLUMN sc_project_qf_model_param.param_type IS '参数类型快照';
COMMENT ON COLUMN sc_project_qf_model_param.param_options IS '可选项快照，JSON 字符串';
COMMENT ON COLUMN sc_project_qf_model_param.param_value IS '用户实际设置值';
COMMENT ON COLUMN sc_project_qf_model_param.section_code IS '参数分组编码';
COMMENT ON COLUMN sc_project_qf_model_param.section_name IS '参数分组名称快照';
COMMENT ON COLUMN sc_project_qf_model_param.section_sort IS '参数分组显示顺序';
COMMENT ON COLUMN sc_project_qf_model_param.sort_no IS '分组内参数显示顺序';
COMMENT ON COLUMN sc_project_qf_model_param.required_flag IS '是否必填';
COMMENT ON COLUMN sc_project_qf_model_param.remark IS '参数说明快照';
COMMENT ON COLUMN sc_project_qf_model_param.create_user_id IS '创建人';
COMMENT ON COLUMN sc_project_qf_model_param.create_org_id IS '创建机构';
COMMENT ON COLUMN sc_project_qf_model_param.create_date IS '创建时间';

-- 基础字典表
CREATE TABLE IF NOT EXISTS pb_base_option (
    id varchar(36) NOT NULL,
    parent_id varchar(36),
    name varchar(200),
    okey varchar(255),
    lable varchar(255),
    ovalue varchar(255),
    sort integer,
    status smallint,
    remark varchar(500),
    item varchar(32),
    CONSTRAINT pk_pb_base_option PRIMARY KEY (id)
);
COMMENT ON TABLE pb_base_option IS '基础字典表';
COMMENT ON COLUMN pb_base_option.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN pb_base_option.parent_id IS '父字典项 UUID，根项为空';
COMMENT ON COLUMN pb_base_option.name IS '字典项名称';
COMMENT ON COLUMN pb_base_option.okey IS '字典分类编码';
COMMENT ON COLUMN pb_base_option.lable IS '字典标签';
COMMENT ON COLUMN pb_base_option.ovalue IS '字典值';
COMMENT ON COLUMN pb_base_option.sort IS '同级排序号';
COMMENT ON COLUMN pb_base_option.status IS '启用状态';
COMMENT ON COLUMN pb_base_option.remark IS '备注';
COMMENT ON COLUMN pb_base_option.item IS '字典辅助标识';

-- 用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id varchar(36) NOT NULL,
    category_id varchar(36),
    account varchar(100),
    number_ bigint,
    pwd varchar(255),
    name varchar(100),
    type_ varchar(32),
    email varchar(254),
    mobile varchar(30),
    orderno integer,
    regtime varchar(19),
    edittime varchar(19),
    logintime varchar(19),
    logintimes bigint,
    status smallint,
    gender varchar(32),
    createuserid varchar(36),
    logintimehistory varchar(19),
    orgadmin smallint,
    uuid varchar(100),
    delete_status smallint,
    loginfailtimes integer,
    lastfailtime varchar(19),
    CONSTRAINT pk_sys_user PRIMARY KEY (id),
    CONSTRAINT uq_sys_user_account UNIQUE (account),
    CONSTRAINT ck_sys_user_orgadmin CHECK (orgadmin IS NULL OR orgadmin IN (0, 1)),
    CONSTRAINT ck_sys_user_delete_status CHECK (delete_status IS NULL OR delete_status IN (0, 1))
);
COMMENT ON TABLE sys_user IS '用户表';
COMMENT ON COLUMN sys_user.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_user.category_id IS '所属机构 UUID，关联 sys_user_category.id；一个用户只归属一个机构';
COMMENT ON COLUMN sys_user.account IS '登录账号，唯一';
COMMENT ON COLUMN sys_user.number_ IS '用户数值编码';
COMMENT ON COLUMN sys_user.pwd IS 'BCrypt 密码哈希';
COMMENT ON COLUMN sys_user.name IS '用户姓名';
COMMENT ON COLUMN sys_user.type_ IS '用户类型';
COMMENT ON COLUMN sys_user.email IS '电子邮箱';
COMMENT ON COLUMN sys_user.mobile IS '手机号';
COMMENT ON COLUMN sys_user.orderno IS '人员选择时的排序权重';
COMMENT ON COLUMN sys_user.regtime IS '注册时间';
COMMENT ON COLUMN sys_user.edittime IS '修改时间';
COMMENT ON COLUMN sys_user.logintime IS '最近登录时间';
COMMENT ON COLUMN sys_user.logintimes IS '累计登录次数';
COMMENT ON COLUMN sys_user.status IS '账号状态';
COMMENT ON COLUMN sys_user.gender IS '性别编码';
COMMENT ON COLUMN sys_user.createuserid IS '创建人 UUID';
COMMENT ON COLUMN sys_user.logintimehistory IS '上一次登录时间';
COMMENT ON COLUMN sys_user.orgadmin IS '历史机构管理员标记；应用已不使用，0否1是';
COMMENT ON COLUMN sys_user.uuid IS '员工编号';
COMMENT ON COLUMN sys_user.delete_status IS '是否删除';
COMMENT ON COLUMN sys_user.loginfailtimes IS '连续登录失败次数';
COMMENT ON COLUMN sys_user.lastfailtime IS '最近一次登录失败时间';

-- 机构表
CREATE TABLE IF NOT EXISTS sys_user_category (
    id varchar(36) NOT NULL,
    parent_id varchar(36),
    name varchar(200),
    longname varchar(500),
    orgtype varchar(32),
    sort integer,
    delete_status smallint,
    orgcode varchar(100),
    buildtype varchar(32),
    activitycode varchar(255),
    CONSTRAINT pk_sys_user_category PRIMARY KEY (id),
    CONSTRAINT ck_sys_user_category_delete_status CHECK (delete_status IS NULL OR delete_status IN (0, 1))
);
COMMENT ON TABLE sys_user_category IS '机构表';
COMMENT ON COLUMN sys_user_category.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_user_category.parent_id IS '上级机构 UUID，根机构为空';
COMMENT ON COLUMN sys_user_category.name IS '机构名称';
COMMENT ON COLUMN sys_user_category.longname IS '机构全称';
COMMENT ON COLUMN sys_user_category.orgtype IS '机构类型编码';
COMMENT ON COLUMN sys_user_category.sort IS '同级排序号';
COMMENT ON COLUMN sys_user_category.delete_status IS '是否删除';
COMMENT ON COLUMN sys_user_category.orgcode IS '机构编码';
COMMENT ON COLUMN sys_user_category.buildtype IS '建设单位类型编码';
COMMENT ON COLUMN sys_user_category.activitycode IS '部门流程编码';

-- 用户登录标识表
CREATE TABLE IF NOT EXISTS sys_user_uid (
    id varchar(36) NOT NULL,
    user_id varchar(36),
    type_ varchar(32),
    uid_ varchar(255),
    enable smallint,
    CONSTRAINT pk_sys_user_uid PRIMARY KEY (id),
    CONSTRAINT ck_sys_user_uid_enable CHECK (enable IS NULL OR enable IN (0, 1))
);
COMMENT ON TABLE sys_user_uid IS '用户登录标识表';
COMMENT ON COLUMN sys_user_uid.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_user_uid.user_id IS '用户 UUID，关联 sys_user.id';
COMMENT ON COLUMN sys_user_uid.type_ IS '登录标识类型，例如 account';
COMMENT ON COLUMN sys_user_uid.uid_ IS '登录标识值';
COMMENT ON COLUMN sys_user_uid.enable IS '是否启用';

-- 角色表
CREATE TABLE IF NOT EXISTS sys_group (
    id varchar(36) NOT NULL,
    categoryid varchar(36),
    name varchar(200),
    code varchar(100),
    description text,
    status smallint,
    createuserid varchar(36),
    createtime varchar(19),
    orderno integer,
    CONSTRAINT pk_sys_group PRIMARY KEY (id),
    CONSTRAINT uq_sys_group_code UNIQUE (code)
);
COMMENT ON TABLE sys_group IS '角色表';
COMMENT ON COLUMN sys_group.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_group.categoryid IS '角色分类 UUID，关联 sys_group_category.id';
COMMENT ON COLUMN sys_group.name IS '角色名称';
COMMENT ON COLUMN sys_group.code IS '角色编码，唯一';
COMMENT ON COLUMN sys_group.description IS '角色说明';
COMMENT ON COLUMN sys_group.status IS '角色状态';
COMMENT ON COLUMN sys_group.createuserid IS '创建人 UUID';
COMMENT ON COLUMN sys_group.createtime IS '创建时间';
COMMENT ON COLUMN sys_group.orderno IS '角色排序号';

-- 角色分类表
CREATE TABLE IF NOT EXISTS sys_group_category (
    id varchar(36) NOT NULL,
    name varchar(200),
    level_ integer,
    sort integer,
    parent_id varchar(36),
    isleaf smallint,
    createuserid varchar(36),
    CONSTRAINT pk_sys_group_category PRIMARY KEY (id),
    CONSTRAINT ck_sys_group_category_isleaf CHECK (isleaf IS NULL OR isleaf IN (0, 1))
);
COMMENT ON TABLE sys_group_category IS '角色分类表';
COMMENT ON COLUMN sys_group_category.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_group_category.name IS '分类名称';
COMMENT ON COLUMN sys_group_category.level_ IS '分类层级';
COMMENT ON COLUMN sys_group_category.sort IS '同级排序号';
COMMENT ON COLUMN sys_group_category.parent_id IS '父分类 UUID，根分类为空';
COMMENT ON COLUMN sys_group_category.isleaf IS '是否叶子分类';
COMMENT ON COLUMN sys_group_category.createuserid IS '创建人 UUID';

-- 用户角色关联表
CREATE TABLE IF NOT EXISTS sys_user_group (
    id varchar(36) NOT NULL,
    userid varchar(36),
    groupid varchar(36),
    status smallint,
    orgid varchar(36),
    CONSTRAINT pk_sys_user_group PRIMARY KEY (id)
);
COMMENT ON TABLE sys_user_group IS '用户角色关联表';
COMMENT ON COLUMN sys_user_group.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_user_group.userid IS '用户 UUID，关联 sys_user.id';
COMMENT ON COLUMN sys_user_group.groupid IS '角色 UUID，关联 sys_group.id';
COMMENT ON COLUMN sys_user_group.status IS '授权状态';
COMMENT ON COLUMN sys_user_group.orgid IS '授权机构 UUID，关联 sys_user_category.id';

-- 角色权限关联表
CREATE TABLE IF NOT EXISTS sys_group_permission (
    id varchar(36) NOT NULL,
    groupid varchar(36),
    permissionid varchar(36),
    status smallint,
    CONSTRAINT pk_sys_group_permission PRIMARY KEY (id)
);
COMMENT ON TABLE sys_group_permission IS '角色权限关联表';
COMMENT ON COLUMN sys_group_permission.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_group_permission.groupid IS '角色 UUID，关联 sys_group.id';
COMMENT ON COLUMN sys_group_permission.permissionid IS '权限 UUID，关联 sys_permission.id';
COMMENT ON COLUMN sys_group_permission.status IS '授权状态';

-- 权限表
CREATE TABLE IF NOT EXISTS sys_permission (
    id varchar(36) NOT NULL,
    name varchar(200),
    module varchar(100),
    permission varchar(255),
    type_ varchar(32),
    description text,
    status smallint,
    categoryid varchar(36),
    orderno integer,
    CONSTRAINT pk_sys_permission PRIMARY KEY (id),
    CONSTRAINT uq_sys_permission_permission UNIQUE (permission)
);
COMMENT ON TABLE sys_permission IS '权限表';
COMMENT ON COLUMN sys_permission.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_permission.name IS '权限名称';
COMMENT ON COLUMN sys_permission.module IS '所属模块编码';
COMMENT ON COLUMN sys_permission.permission IS '权限标识';
COMMENT ON COLUMN sys_permission.type_ IS '权限类型';
COMMENT ON COLUMN sys_permission.description IS '权限说明';
COMMENT ON COLUMN sys_permission.status IS '权限状态';
COMMENT ON COLUMN sys_permission.categoryid IS '权限分类 UUID，关联 sys_permission_category.id';
COMMENT ON COLUMN sys_permission.orderno IS '权限排序号';

-- 权限分类表
CREATE TABLE IF NOT EXISTS sys_permission_category (
    id varchar(36) NOT NULL,
    parent_id varchar(36),
    name varchar(200),
    sort integer,
    remark varchar(500),
    CONSTRAINT pk_sys_permission_category PRIMARY KEY (id)
);
COMMENT ON TABLE sys_permission_category IS '权限分类表';
COMMENT ON COLUMN sys_permission_category.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_permission_category.parent_id IS '父分类 UUID，根分类为空';
COMMENT ON COLUMN sys_permission_category.name IS '分类名称';
COMMENT ON COLUMN sys_permission_category.sort IS '同级排序号';
COMMENT ON COLUMN sys_permission_category.remark IS '备注';

-- 用户直接权限关联表
CREATE TABLE IF NOT EXISTS sys_user_permission (
    id varchar(36) NOT NULL,
    userid varchar(36),
    permissionid varchar(36),
    orgid varchar(36),
    CONSTRAINT pk_sys_user_permission PRIMARY KEY (id)
);
COMMENT ON TABLE sys_user_permission IS '用户直接权限关联表';
COMMENT ON COLUMN sys_user_permission.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_user_permission.userid IS '用户 UUID，关联 sys_user.id';
COMMENT ON COLUMN sys_user_permission.permissionid IS '权限 UUID，关联 sys_permission.id';
COMMENT ON COLUMN sys_user_permission.orgid IS '授权机构 UUID，关联 sys_user_category.id';

-- 资源表
CREATE TABLE IF NOT EXISTS sys_resource (
    id varchar(36) NOT NULL,
    menuid varchar(36),
    name varchar(200),
    module varchar(100),
    resource_ varchar(1000),
    type varchar(32),
    description text,
    categoryid varchar(36),
    status smallint,
    CONSTRAINT pk_sys_resource PRIMARY KEY (id)
);
COMMENT ON TABLE sys_resource IS '资源表';
COMMENT ON COLUMN sys_resource.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_resource.menuid IS '关联菜单 UUID，可为空';
COMMENT ON COLUMN sys_resource.name IS '资源名称';
COMMENT ON COLUMN sys_resource.module IS '所属模块编码';
COMMENT ON COLUMN sys_resource.resource_ IS '资源标识或路径';
COMMENT ON COLUMN sys_resource.type IS '资源类型';
COMMENT ON COLUMN sys_resource.description IS '资源说明';
COMMENT ON COLUMN sys_resource.categoryid IS '资源分类 UUID，关联 sys_resource_category.id';
COMMENT ON COLUMN sys_resource.status IS '资源状态';

-- 资源分类表
CREATE TABLE IF NOT EXISTS sys_resource_category (
    id varchar(36) NOT NULL,
    parent_id varchar(36),
    name varchar(200),
    module varchar(100),
    sort integer,
    remark varchar(500),
    CONSTRAINT pk_sys_resource_category PRIMARY KEY (id)
);
COMMENT ON TABLE sys_resource_category IS '资源分类表';
COMMENT ON COLUMN sys_resource_category.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_resource_category.parent_id IS '父分类 UUID，根分类为空';
COMMENT ON COLUMN sys_resource_category.name IS '分类名称';
COMMENT ON COLUMN sys_resource_category.module IS '所属模块编码';
COMMENT ON COLUMN sys_resource_category.sort IS '同级排序号';
COMMENT ON COLUMN sys_resource_category.remark IS '备注';

-- 权限资源关联表
CREATE TABLE IF NOT EXISTS sys_permission_resource (
    id varchar(36) NOT NULL,
    permissionid varchar(36),
    resourceid varchar(36),
    CONSTRAINT pk_sys_permission_resource PRIMARY KEY (id)
);
COMMENT ON TABLE sys_permission_resource IS '权限资源关联表';
COMMENT ON COLUMN sys_permission_resource.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_permission_resource.permissionid IS '权限 UUID，关联 sys_permission.id';
COMMENT ON COLUMN sys_permission_resource.resourceid IS '资源 UUID，关联 sys_resource.id';

-- 菜单表
CREATE TABLE IF NOT EXISTS sys_menu (
    id varchar(36) NOT NULL,
    parent_id varchar(36),
    code varchar(100),
    title varchar(200),
    url varchar(500),
    view_ smallint,
    remark varchar(500),
    icon varchar(100),
    isleaf smallint,
    level_ integer,
    expanded smallint,
    type smallint,
    name varchar(100),
    CONSTRAINT pk_sys_menu PRIMARY KEY (id),
    CONSTRAINT uq_sys_menu_code UNIQUE (code),
    CONSTRAINT ck_sys_menu_view CHECK (view_ IS NULL OR view_ IN (0, 1)),
    CONSTRAINT ck_sys_menu_isleaf CHECK (isleaf IS NULL OR isleaf IN (0, 1)),
    CONSTRAINT ck_sys_menu_expanded CHECK (expanded IS NULL OR expanded IN (0, 1))
);
COMMENT ON TABLE sys_menu IS '菜单表';
COMMENT ON COLUMN sys_menu.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_menu.parent_id IS '父菜单 UUID，根菜单为空';
COMMENT ON COLUMN sys_menu.code IS '菜单编码';
COMMENT ON COLUMN sys_menu.title IS '菜单标题';
COMMENT ON COLUMN sys_menu.url IS '路由地址';
COMMENT ON COLUMN sys_menu.view_ IS '是否显示';
COMMENT ON COLUMN sys_menu.remark IS '备注';
COMMENT ON COLUMN sys_menu.icon IS '图标标识';
COMMENT ON COLUMN sys_menu.isleaf IS '是否叶子菜单';
COMMENT ON COLUMN sys_menu.level_ IS '菜单层级';
COMMENT ON COLUMN sys_menu.expanded IS '是否默认展开';
COMMENT ON COLUMN sys_menu.type IS '菜单类型';
COMMENT ON COLUMN sys_menu.name IS '菜单名称';

-- 操作日志表
CREATE TABLE IF NOT EXISTS sys_operation_log (
    id varchar(36) NOT NULL,
    userid varchar(36),
    account varchar(100),
    name varchar(100),
    orgid varchar(36),
    ip varchar(45),
    area varchar(100),
    time varchar(19),
    module varchar(100),
    action varchar(200),
    description varchar(500),
    status varchar(16),
    spend numeric(12,4),
    target varchar(500),
    errormsg text,
    CONSTRAINT pk_sys_operation_log PRIMARY KEY (id)
);
COMMENT ON TABLE sys_operation_log IS '操作日志表';
COMMENT ON COLUMN sys_operation_log.id IS 'Java 生成 UUID，主键';
COMMENT ON COLUMN sys_operation_log.userid IS '操作用户 UUID';
COMMENT ON COLUMN sys_operation_log.account IS '操作账号快照';
COMMENT ON COLUMN sys_operation_log.name IS '操作人姓名快照';
COMMENT ON COLUMN sys_operation_log.orgid IS '操作机构 UUID';
COMMENT ON COLUMN sys_operation_log.ip IS '客户端 IP，兼容 IPv6';
COMMENT ON COLUMN sys_operation_log.area IS '访问地区';
COMMENT ON COLUMN sys_operation_log.time IS '操作时间';
COMMENT ON COLUMN sys_operation_log.module IS '所属模块';
COMMENT ON COLUMN sys_operation_log.action IS '操作动作';
COMMENT ON COLUMN sys_operation_log.description IS '操作说明';
COMMENT ON COLUMN sys_operation_log.status IS '执行状态';
COMMENT ON COLUMN sys_operation_log.spend IS '操作耗时';
COMMENT ON COLUMN sys_operation_log.target IS '操作目标';
COMMENT ON COLUMN sys_operation_log.errormsg IS '错误信息';

-- 表间 ID 关联和文件删除时的派生数据清理由业务代码维护；数据库不设置外键。

-- 同一项目仅有一个组价中批次。
-- 每个项目最多一个根 CBS 节点。
CREATE UNIQUE INDEX IF NOT EXISTS uq_sc_project_cbs_root ON sc_project_cbs (project_id) WHERE parent_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_sc_file_master ON sc_file (master_type, master_id);
CREATE INDEX IF NOT EXISTS ix_sc_file_item_file_parent_sort ON sc_file_item (file_id, parent_id, sort_no);
CREATE INDEX IF NOT EXISTS ix_sc_match_consume_match ON sc_file_item_match_consume (match_id);
CREATE INDEX IF NOT EXISTS ix_sc_match_file_item ON sc_file_item_match (file_item_id);
CREATE INDEX IF NOT EXISTS ix_sc_match_relation_associated ON sc_file_item_match_relation (associated_match_id);
CREATE INDEX IF NOT EXISTS ix_sc_history_cbs_tree ON sc_history_project_cbs (history_project_id, parent_id, sort_no);
CREATE INDEX IF NOT EXISTS ix_sc_history_item_tree ON sc_history_project_item (history_project_cbs_id, parent_id, sort_no);
CREATE INDEX IF NOT EXISTS ix_sc_history_consume_item_sort ON sc_history_project_consume (history_project_item_id, sort_no);
CREATE INDEX IF NOT EXISTS ix_sc_flow_log_master ON sc_flow_log (task_type, master_id);
CREATE INDEX IF NOT EXISTS ix_sc_price_code ON sc_price (code);
CREATE INDEX IF NOT EXISTS ix_pb_base_option_okey_sort ON pb_base_option (okey, sort);
ALTER TABLE sys_menu DROP COLUMN IF EXISTS sort;

-- 将旧版时间列和布尔列迁移到当前文本格式及 SMALLINT 0/1。
DO $$
DECLARE
    item record;
    current_type text;
BEGIN
    FOR item IN SELECT * FROM (VALUES
        ('sc_project', 'create_date'),
        ('sc_batch', 'pricing_completed_at'), ('sc_batch', 'calculation_completed_at'), ('sc_batch', 'create_date'),
        ('sc_file', 'create_date'), ('sc_file_header', 'create_date'), ('sc_file_item', 'create_date'),
        ('sc_file_item_match', 'create_date'), ('sc_file_item_match_consume', 'create_date'),
        ('sc_history_project', 'create_date'), ('sc_match_experience', 'create_date'),
        ('sc_task', 'refer_date'), ('sc_task', 'audit_date'), ('sc_flow_log', 'refer_date'), ('sc_flow_log', 'audit_date'),
        ('sc_cbs', 'create_date'), ('sc_cbs_detail', 'create_date'), ('sc_project_cbs', 'create_date'),
        ('sc_price', 'create_date'), ('sc_project_cbs_de_library', 'create_date'),
        ('sc_project_qf_model', 'create_date'), ('sc_project_qf_model_param', 'create_date'),
        ('sys_user', 'regtime'), ('sys_user', 'edittime'), ('sys_user', 'logintime'),
        ('sys_user', 'logintimehistory'), ('sys_user', 'lastfailtime'),
        ('sys_group', 'createtime'), ('sys_operation_log', 'time')
    ) AS columns_(table_name, column_name)
    LOOP
        SELECT data_type INTO current_type FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = item.table_name AND column_name = item.column_name;

        IF current_type = 'timestamp with time zone' THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE varchar(19) USING to_char(%I AT TIME ZONE %L, %L)',
                item.table_name, item.column_name, item.column_name, 'UTC', 'YYYY-MM-DD HH24:MI:SS');
        ELSIF current_type = 'timestamp without time zone' THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE varchar(19) USING to_char(%I, %L)',
                item.table_name, item.column_name, item.column_name, 'YYYY-MM-DD HH24:MI:SS');
        ELSIF current_type IN ('character varying', 'text') THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE varchar(19) USING replace(left(%I::text, 19), %L, %L)',
                item.table_name, item.column_name, item.column_name, 'T', ' ');
        END IF;
    END LOOP;

    FOR item IN SELECT * FROM (VALUES
        ('sc_qf_model_param', 'required_flag', 'ck_sc_qf_model_param_required_flag'),
        ('sc_project_qf_model_param', 'required_flag', 'ck_sc_project_qf_model_param_required_flag'),
        ('sys_user', 'orgadmin', 'ck_sys_user_orgadmin'), ('sys_user', 'delete_status', 'ck_sys_user_delete_status'),
        ('sys_user_category', 'delete_status', 'ck_sys_user_category_delete_status'),
        ('sys_user_uid', 'enable', 'ck_sys_user_uid_enable'),
        ('sys_group_category', 'isleaf', 'ck_sys_group_category_isleaf'),
        ('sys_menu', 'view_', 'ck_sys_menu_view'), ('sys_menu', 'isleaf', 'ck_sys_menu_isleaf'),
        ('sys_menu', 'expanded', 'ck_sys_menu_expanded')
    ) AS flags(table_name, column_name, constraint_name)
    LOOP
        SELECT data_type INTO current_type FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = item.table_name AND column_name = item.column_name;

        IF current_type = 'boolean' THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE smallint USING CASE WHEN %I IS TRUE THEN 1 WHEN %I IS FALSE THEN 0 ELSE NULL END',
                item.table_name, item.column_name, item.column_name, item.column_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = item.constraint_name
              AND conrelid = to_regclass(format('%I.%I', current_schema(), item.table_name))
        ) THEN
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I CHECK (%I IS NULL OR %I IN (0, 1))',
                item.table_name, item.constraint_name, item.column_name, item.column_name);
        END IF;
    END LOOP;
END;
$$;

-- 为旧库补齐新结构中定义的系统编码唯一约束。
CREATE UNIQUE INDEX IF NOT EXISTS uq_sys_menu_code ON sys_menu (code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sys_permission_permission ON sys_permission (permission);

COMMIT;
