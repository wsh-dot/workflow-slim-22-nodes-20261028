"""现有表的参数化访问；连接使用 autocommit，模型请求不持有数据库事务。"""
from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from config import Config, Trace
from analysis_snapshot import (SCHEMA_VERSION, finalize_snapshot, fingerprint, input_source,
                               json_text, validate_snapshot)
from execution_profile import digest, execution_profile, require_frozen_profile

ITEM_COLUMNS = ("id", "file_id", "project_cbs_id", "parent_id", "sort_no", "type", "code", "name",
                "specification", "unit", "quantity", "remark", "cbs_match_status", "cbs_match_method",
                "create_user_id", "create_org_id", "create_date")


class Repository:
    def __init__(self, connection, config: Config):
        if not connection.autocommit:
            raise ValueError("数据库连接必须开启 autocommit，保存时再显式开启单文件事务")
        self.connection = connection
        self.config = config
        self._claimed_task = None
        self._task_lock_key = None
        self._execution = None

    def freeze_execution(self, task, cbs):
        """首次执行记录在现有任务行；换request_id不解除同一task_id的版本约束。"""
        self._require_claimed_task(task)
        profile = execution_profile(self.config, cbs)
        expected = digest(profile)
        with self.connection.transaction():
            self._require_active_task(lock=True)
            with self.connection.cursor() as cur:
                cur.execute('SELECT execution_profile FROM sc_ai_python_task WHERE id=%s', (task['id'],))
                frozen = cur.fetchone()['execution_profile']
                if frozen is None:
                    cur.execute('SELECT 1 FROM sc_file_analysis_snapshot WHERE task_id=%s LIMIT 1', (task['id'],))
                    if cur.fetchone():
                        raise ValueError('任务已有成功快照但缺少冻结版本，禁止混用，需明确新的任务边界')
                    frozen = {'schema_version': '1.0', 'state': 'FROZEN',
                              'project_id': task['project_id'], 'batch_id': task['batch_id'],
                              'profile_fingerprint': expected, 'profile_data': profile,
                              'frozen_at': datetime.now(timezone.utc).isoformat()}
                    cur.execute('UPDATE sc_ai_python_task SET execution_profile=%s WHERE id=%s',
                                (Jsonb(frozen), task['id']))
                if require_frozen_profile(frozen, task) != expected:
                    raise ValueError('同一任务冻结配置或源码已变化；拒绝混用，需明确新的任务边界')
        self._execution = {'fingerprint': expected, 'cbs': cbs}

    def check_execution(self, *, lock=False):
        if self._execution is None:
            if self._claimed_task is not None or self.config.task_scope_mode == 'backend_queue':
                raise ValueError('任务尚未冻结执行版本，禁止模型调用或提交')
            # Unclaimed approved_scope use is retained only for isolated storage tools.
            return
        if digest(execution_profile(self.config, self._execution['cbs'])) != self._execution['fingerprint']:
            raise ValueError('运行期间源码、模板或配置变化，停止原冻结运行')
        self._require_active_task(lock=lock)
        with self.connection.cursor() as cur:
            cur.execute('SELECT execution_profile FROM sc_ai_python_task WHERE id=%s',
                        (self._claimed_task['id'],))
            frozen = cur.fetchone()['execution_profile']
        if require_frozen_profile(frozen, self._claimed_task) != self._execution['fingerprint']:
            raise ValueError('任务执行冻结记录已变化，拒绝旧运行')
        if lock:
            # Brief commit barrier also covers new candidate inserts (row locks alone miss phantoms).
            with self.connection.cursor() as cur:
                cur.execute('LOCK TABLE sc_project_cbs IN SHARE MODE')
            if digest(self.load_cbs(self._claimed_task['project_id'])) != digest(self._execution['cbs']):
                raise ValueError('CBS候选版本已变化，拒绝旧范围判断提交')

    def _try_task_lock(self, task):
        """同一批次只允许一个会话处理，不靠扩展status值领取。"""
        if self._task_lock_key is not None:
            return False
        identity = f"smart-cost:quantity:{task['project_id']}:{task['batch_id']}".encode("utf-8")
        key = int.from_bytes(hashlib.sha256(identity).digest()[:8], "big", signed=True)
        unsigned = key & ((1 << 64) - 1)
        with self.connection.cursor() as cur:
            # 会话锁可重入；同一连接上的另一个Repository也不能借用已有锁。
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' "
                        "AND pid=pg_backend_pid() AND classid=%s::oid AND objid=%s::oid AND objsubid=1) AS held",
                        (unsigned >> 32, unsigned & 0xffffffff))
            if cur.fetchone()["held"]:
                return False
            cur.execute("SELECT pg_try_advisory_lock(%s::bigint) AS acquired", (key,))
            if not cur.fetchone()["acquired"]:
                return False
        self._task_lock_key = key
        return True

    def release_task(self, task):
        """完成、失败或异常退出时释放本会话的批次锁；连接关闭也会自动释放。"""
        if self._claimed_task is not None:
            self._require_claimed_task(task)
        if self._task_lock_key is not None and not self.connection.closed:
            with self.connection.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s::bigint) AS released", (self._task_lock_key,))
                if not cur.fetchone()["released"]:
                    raise RuntimeError("当前Runner的任务独占锁已丢失")
        self._task_lock_key = None
        self._claimed_task = None
        self._execution = None

    def _task_identity(self, task):
        return tuple(task.get(key) for key in ("id", "project_id", "batch_id", "request_id", "create_user_id", "create_org_id", "create_date"))

    def _require_claimed_task(self, task):
        if self._claimed_task is None or self._task_identity(task) != self._task_identity(self._claimed_task):
            raise ValueError("任务尚未由本Runner领取，或任务归属/审计信息发生变化")

    def _require_active_task(self, *, lock=False):
        """模型期间外部可能结束任务；读取下一文件和提交前重新核对。"""
        task = self._claimed_task
        if task is None:
            raise ValueError("任务尚未领取")
        params = [task['id'], task['project_id'], task['batch_id'], self.config.business['quantity_task_type'], '0']
        guard = ''
        if self.config.task_scope_mode == 'backend_queue':
            guard = ' AND request_id=%s AND create_user_id=%s AND create_org_id IS NOT DISTINCT FROM %s AND create_date=%s'
            params.extend((task['request_id'], task['create_user_id'], task.get('create_org_id'), task['create_date']))
        with self.connection.cursor() as cur:
            cur.execute('SELECT id FROM sc_ai_python_task WHERE id=%s AND project_id=%s AND batch_id=%s '
                        'AND task_type=%s AND status=%s' + guard + (' FOR UPDATE' if lock else ''), params)
            if cur.fetchone() is None:
                raise RuntimeError('任务已结束或归属已变化，停止处理并保留现有任务结果')

    def _require_input_scope(self, *, batch_id=None, project_id=None):
        if self.config.task_scope_mode == "backend_queue":
            if self._claimed_task is None:
                raise ValueError("读取任务输入前必须先成功领取后端任务")
            if batch_id is not None and batch_id != self._claimed_task["batch_id"]:
                raise ValueError("批次不属于当前领取的任务")
            if project_id is not None and project_id != self._claimed_task["project_id"]:
                raise ValueError("项目不属于当前领取的任务")
        elif ((batch_id is not None and batch_id not in {s["batch_id"] for s in self.config.approved_scope})
              or (project_id is not None and project_id not in {s["project_id"] for s in self.config.approved_scope})):
            raise ValueError("项目或批次不在获准范围")

    def find_waiting_task(self) -> dict | None:
        """正常模式读取经后端创建的工程量队列，隔离验证模式才按固定项目筛选。"""
        params = [self.config.business["quantity_task_type"], self.config.business["task_waiting"]]
        if self.config.task_scope_mode == "backend_queue":
            scope_sql = ("b.current_stage=ANY(%s) AND t.request_id ~* "
                         "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "
                         "AND NULLIF(btrim(t.create_user_id),'') IS NOT NULL "
                         "AND NULLIF(btrim(t.create_date),'') IS NOT NULL")
            params.append(self.config.business.get("task_batch_stages", [self.config.business["quantity_task_type"]]))
        else:
            scope_sql = " OR ".join("(t.project_id=%s AND t.batch_id=%s)" for _ in self.config.approved_scope)
            for scope in self.config.approved_scope:
                params.extend((scope["project_id"], scope["batch_id"]))
        if self._claimed_task is not None:
            return None
        busy_batches = []
        while True:
            with self.connection.cursor() as cur:
                cur.execute("SELECT t.* FROM sc_ai_python_task t JOIN sc_batch b ON b.id=t.batch_id "
                            "AND b.project_id=t.project_id WHERE t.task_type=%s AND t.status=%s AND (" + scope_sql +
                            ") AND t.batch_id <> ALL(%s::text[]) ORDER BY t.create_date,t.id LIMIT 1", params + [busy_batches])
                task = cur.fetchone()
            if task is None:
                return None
            if self._try_task_lock(task):
                self.release_task(task)
                logging.info("waiting_task_found task=%s project=%s batch=%s status=%s", task["id"], task["project_id"], task["batch_id"], task["status"])
                return task
            busy_batches.append(task["batch_id"])

    def find_next_file(self, batch_id: str) -> dict | None:
        """仅查询当前批次的 1002/1102/2101，不用关联输入资料过滤缺失文件。"""
        self._require_input_scope(batch_id=batch_id)
        if self._claimed_task is not None:
            self._require_active_task()
        b = self.config.business
        with self.connection.cursor() as cur:
            cur.execute("SELECT * FROM sc_file WHERE master_id=%s AND master_type=%s AND type=%s "
                        "AND status=ANY(%s) ORDER BY create_date,id LIMIT 1",
                        (batch_id, b["batch_master_type"], b["material_file_type"], b["pending_file_statuses"]))
            file = cur.fetchone()
        logging.info("next_file_queried batch=%s source=1002 type=1102 status=2101 file=%s",
                     batch_id, file["id"] if file else None)
        return file

    def load_header(self, file_id: str) -> dict:
        """表头必须恰有一条；字段为空时保留原值。"""
        with self.connection.cursor() as cur:
            cur.execute("SELECT * FROM sc_file_header WHERE file_id=%s", (file_id,))
            headers = cur.fetchall()
        if len(headers) != 1:
            raise ValueError(f"料表表头应为一条，实际 {len(headers)} 条")
        return headers[0]

    def load_rows(self, file_id: str) -> list:
        """按唯一且非空的 orderno 保留完整原始行；不按序号或 UUID 猜测。"""
        with self.connection.cursor() as cur:
            cur.execute("SELECT * FROM sc_file_raw WHERE file_id=%s ORDER BY orderno", (file_id,))
            rows = cur.fetchall()
        order = [r.get("orderno") for r in rows]
        if not rows or None in order or len(set(order)) != len(order):
            raise ValueError("原始行缺失或 orderno 无法唯一确定原表顺序")
        if len({r["id"] for r in rows}) != len(rows):
            raise ValueError("原始行 ID 重复")
        return rows

    def load_file_input(self, file: dict) -> dict:
        """短事务冻结同一输入版本；源表触发器与文件行共享锁协调，模型调用不持锁。"""
        self._require_input_scope(batch_id=file["master_id"])
        with self.connection.transaction():
            if self._claimed_task is not None:
                self._require_active_task()
            with self.connection.cursor() as cur:
                cur.execute("SELECT input_revision,status,master_id,master_type,type FROM sc_file WHERE id=%s FOR SHARE", (file["id"],))
                current = cur.fetchone()
                if (not current or current["status"] != "2101" or current["master_id"] != file["master_id"]
                        or current["master_type"] != "1002" or current["type"] != "1102"):
                    raise ValueError("冻结输入时文件归属或待处理状态已变化")
                revision = current["input_revision"]
                if type(revision) is not int or revision < 1:
                    raise ValueError("缺少有效输入版本，请先执行0902快照迁移")
                return {"input_revision": revision, "header": self.load_header(file["id"]),
                        "raw_rows": self.load_rows(file["id"])}

    def load_cbs(self, project_id: str) -> list:
        """读取当前项目真实名称和父关系；不从其他项目补候选。"""
        self._require_input_scope(project_id=project_id)
        with self.connection.cursor() as cur:
            cur.execute("SELECT id,parent_id,name,category_code,category_name,sort_no FROM sc_project_cbs "
                        "WHERE project_id=%s ORDER BY sort_no,id", (project_id,))
            return cur.fetchall()

    def _clear_file_results(self, cur, file_id: str, batch_id: str) -> None:
        """删除旧工程量及共享下游成果；不清理其他批次的数据。"""
        cur.execute("SELECT id FROM sc_file_item WHERE file_id=%s", (file_id,))
        item_ids = [row["id"] for row in cur.fetchall()]
        if not item_ids:
            return
        # 消耗可能直接引用工程量，汇总匹配的file_item_id也可能为空。
        # UNION去重使双向关系中的环也能终止。
        cur.execute("""
            WITH RECURSIVE affected(id) AS (
                (SELECT id FROM sc_file_item_match WHERE file_item_id=ANY(%s)
                 UNION
                 SELECT match_id FROM sc_file_item_match_consume
                 WHERE source_file_item_id=ANY(%s) AND match_id IS NOT NULL)
                UNION
                SELECT CASE WHEN r.source_match_id=a.id THEN r.associated_match_id
                            ELSE r.source_match_id END
                FROM affected a JOIN sc_file_item_match_relation r
                  ON r.source_match_id=a.id OR r.associated_match_id=a.id
            )
            SELECT id FROM affected
            """, (item_ids, item_ids))
        match_ids = [row["id"] for row in cur.fetchall()]
        # 共享成果可以涉及本批次其他料表，但不能顺着异常引用删除其他批次。
        cur.execute("""
            SELECT 1 FROM (
                SELECT file_item_id AS item_id FROM sc_file_item_match
                WHERE id=ANY(%s) AND file_item_id IS NOT NULL
                UNION
                SELECT source_file_item_id FROM sc_file_item_match_consume
                WHERE match_id=ANY(%s) AND source_file_item_id IS NOT NULL
            ) sources
            LEFT JOIN sc_file_item i ON i.id=sources.item_id
            LEFT JOIN sc_file f ON f.id=i.file_id
            WHERE f.master_id IS DISTINCT FROM %s OR f.master_type IS DISTINCT FROM '1002'
               OR f.type IS DISTINCT FROM '1102'
            LIMIT 1
            """, (match_ids, match_ids, batch_id))
        if cur.fetchone():
            raise ValueError("关联成果包含当前批次以外的来源，拒绝跨批次清理")
        cur.execute("DELETE FROM sc_file_item_match_relation "
                    "WHERE source_match_id=ANY(%s) OR associated_match_id=ANY(%s)", (match_ids, match_ids))
        cur.execute("DELETE FROM sc_file_item_match_consume "
                    "WHERE match_id=ANY(%s) OR source_file_item_id=ANY(%s)", (match_ids, item_ids))
        cur.execute("DELETE FROM sc_file_item_match WHERE id=ANY(%s)", (match_ids,))
        cur.execute("DELETE FROM sc_file_item WHERE file_id=%s", (file_id,))

    def save_file_result(self, file: dict, items: list, task: dict, trace: Trace, snapshot: dict) -> None:
        """锁定并复核输入，工程量、版本快照和2102同事务提交；快照失败不降级。"""
        seen = set()
        for item in items:
            if set(item) != set(ITEM_COLUMNS) or item["file_id"] != file["id"]:
                raise ValueError("节点列或文件归属错误")
            if item["id"] in seen or (item["parent_id"] is not None and item["parent_id"] not in seen):
                raise ValueError("节点 ID 重复，或父节点未先写入")
            if item["type"] not in {None, self.config.business["item_types"]["MATERIAL"], self.config.business["item_types"]["EQUIPMENT"]}:
                raise ValueError("工程量结果只允许设备、主材或类型待确认，分部结构项不得入库")
            seen.add(item["id"])
        if self.config.task_scope_mode == "backend_queue":
            self._require_claimed_task(task)
        elif {"project_id": task["project_id"], "batch_id": task["batch_id"]} not in self.config.approved_scope:
            raise ValueError("任务不在获准范围")
        validate_snapshot(snapshot, file, task, items)
        trace.write("save_started", item_count=len(items))
        try:
            with self.connection.transaction():
                with self.connection.cursor() as cur:
                    self.check_execution(lock=True)
                    if self._claimed_task is not None:
                        self._require_active_task(lock=True)
                    cur.execute("SELECT f.* FROM sc_file f JOIN sc_batch b ON b.id=f.master_id "
                                "WHERE f.id=%s AND b.id=%s AND b.project_id=%s FOR UPDATE OF f",
                                (file["id"], task["batch_id"], task["project_id"]))
                    current = cur.fetchone()
                    b = self.config.business
                    if not current or current["status"] != "2101" or current["master_type"] != "1002" or current["type"] != "1102":
                        raise ValueError("文件归属或待处理状态已变化，拒绝保存")
                    if current["input_revision"] != snapshot["provenance"]["input_revision"]:
                        raise ValueError("模型处理期间原始输入已变化，拒绝保存旧输入结果")
                    source = input_source(self.load_header(file["id"]), self.load_rows(file["id"]))
                    if fingerprint(source) != snapshot["provenance"]["input_fingerprint"]:
                        raise ValueError("原始输入指纹已变化，拒绝保存")
                    # 文件锁串行分配版本；MAX只用于编号，不作为快照有效性判断。
                    cur.execute("SELECT COALESCE(MAX(result_revision),0)+1 AS next_revision "
                                "FROM sc_file_analysis_snapshot WHERE file_id=%s", (file["id"],))
                    result_revision = cur.fetchone()["next_revision"]
                    self._clear_file_results(cur, file["id"], task["batch_id"])
                    if items:
                        cur.executemany("INSERT INTO sc_file_item (" + ",".join(ITEM_COLUMNS) + ") VALUES (" +
                                        ",".join(["%s"] * len(ITEM_COLUMNS)) + ")",
                                        [tuple(item[k] for k in ITEM_COLUMNS) for item in items])
                    cur.execute("SELECT " + ",".join(ITEM_COLUMNS) + " FROM sc_file_item WHERE file_id=%s", (file["id"],))
                    persisted_items = cur.fetchall()
                    saved_snapshot = finalize_snapshot(snapshot, persisted_items, result_revision)
                    by_id = {item["id"]: item for item in persisted_items}
                    validate_snapshot(saved_snapshot, file, task, [by_id[item["id"]] for item in saved_snapshot["items"]])
                    snapshot_id = str(uuid4())
                    cur.execute("INSERT INTO sc_file_analysis_snapshot "
                                "(id,file_id,task_id,input_revision,result_revision,snapshot_schema_version,snapshot_data,"
                                "create_user_id,create_org_id,create_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (snapshot_id, file["id"], task["id"], current["input_revision"], result_revision, SCHEMA_VERSION,
                                 Jsonb(saved_snapshot, dumps=json_text), task["create_user_id"], task.get("create_org_id"),
                                 datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
                    cur.execute("UPDATE sc_file SET status=%s WHERE id=%s AND status=%s",
                                (b["file_completed"], file["id"], "2101"))
                    if cur.rowcount != 1:
                        raise ValueError("文件状态更新未命中唯一记录")
        except BaseException as exc:
            trace.write("save_rolled_back", error_type=type(exc).__name__)
            raise
        trace.write("save_committed", item_count=len(items), file_status="2102", snapshot_id=snapshot_id,
                    input_revision=current["input_revision"], result_revision=result_revision,
                    snapshot_schema_version=SCHEMA_VERSION)

    def set_task_status(self, task: dict, status: str, error_message: str | None = None) -> bool:
        """持会话锁复核并领取0；结束写1，用error_message区分成功和失败。"""
        b = self.config.business
        if self.config.task_scope_mode == 'approved_only' and {
                'project_id': task['project_id'], 'batch_id': task['batch_id']} not in self.config.approved_scope:
            raise ValueError('任务不在获准范围')
        queue_mode = self.config.task_scope_mode == "backend_queue"
        if queue_mode:
            try:
                request_id = task.get("request_id", "")
                valid_request = str(UUID(request_id)) == request_id.lower()
            except (ValueError, TypeError, AttributeError):
                valid_request = False
            if not valid_request or not task.get("create_user_id") or not task.get("create_date"):
                raise ValueError("后端任务缺少有效请求ID或创建人/创建时间")
        elif {"project_id": task["project_id"], "batch_id": task["batch_id"]} not in self.config.approved_scope:
            raise ValueError("任务不在获准范围")
        if status not in {b[k] for k in ("task_processing", "task_completed", "task_failed")}:
            raise ValueError("非法任务目标状态")
        claiming = status == b["task_processing"]
        if claiming:
            if self._claimed_task is not None or not self._try_task_lock(task):
                return False
            if error_message is not None:
                self.release_task(task)
                raise ValueError("领取任务不能写入失败信息")
        else:
            self._require_claimed_task(task)
        if error_message is not None and not isinstance(error_message, str):
            raise ValueError("任务错误信息必须为文本或空")
        error_message = error_message.strip() or None if error_message is not None else None
        expected = b["task_waiting"]
        params = [status, error_message, task["id"], task["project_id"], task["batch_id"], b["quantity_task_type"], expected]
        guard_sql = ""
        if queue_mode:
            guard_sql = (" AND request_id=%s AND create_user_id=%s AND create_org_id IS NOT DISTINCT FROM %s AND create_date=%s "
                         "AND EXISTS (SELECT 1 FROM sc_batch b WHERE b.id=sc_ai_python_task.batch_id "
                         "AND b.project_id=sc_ai_python_task.project_id AND b.current_stage=ANY(%s))")
            params.extend((task["request_id"], task["create_user_id"], task.get("create_org_id"), task["create_date"]))
            params.append(b.get("task_batch_stages", [b["quantity_task_type"]]))
        try:
            with self.connection.cursor() as cur:
                cur.execute("UPDATE sc_ai_python_task SET status=%s,error_message=%s WHERE id=%s AND project_id=%s "
                            "AND batch_id=%s AND task_type=%s AND status=%s" + guard_sql, params)
                updated = cur.rowcount == 1
        except BaseException:
            if claiming:
                self.release_task(task)
            raise
        if claiming and updated:
            self._claimed_task = dict(task)
        elif claiming or updated:
            self.release_task(task)
        logging.info("task_status task=%s target=%s updated=%s", task["id"], status, updated)
        return updated
