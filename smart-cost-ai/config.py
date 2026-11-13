"""运行配置及本地诊断；不从料表正文读取配置或凭据。"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


class ConfigurationError(ValueError):
    """运行配置不完整或与工程量编制契约冲突。"""


@dataclass(frozen=True)
class Config:
    model: dict = field(repr=False)
    database: dict = field(repr=False)
    business: dict
    classification_rules: list
    approved_scope: list
    log_dir: Path
    poll_seconds: float = 3
    prompt_dir: Path = Path(__file__).parent / "prompts"
    task_scope_mode: str = "approved_only"
    analysis_options: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path, *, require_secrets: bool = True) -> "Config":
        """生产入口领取后端任务；旧配置保留固定范围语义，不能因升级自动扩大处理范围。"""
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        # 用户选用项目.env作为本地配置；明确值优先于机器遗留环境，不展开${...}。
        file_env = dotenv_values(path.parent / ".env", encoding="utf-8-sig", interpolate=False)
        runtime_env = {**os.environ, **{key: value for key, value in file_env.items() if value is not None}}
        provider = data.get("active_provider")
        if provider not in {"mobile_cloud", "aliyun_bailian"}:
            raise ConfigurationError("active_provider 必须选择 mobile_cloud 或 aliyun_bailian")
        model = dict(data.get("providers", {}).get(provider, {}))
        model.update(provider=provider)
        for key in ("base_url", "model", "api_key_env"):
            if not isinstance(model.get(key), str) or not model[key].strip():
                raise ConfigurationError(f"所选供应商缺少 {key}")
        url = urlsplit(model["base_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ConfigurationError("模型地址必须是无凭据、无查询参数的 HTTPS 地址")
        if model.get("api_style") != "chat_completions":
            raise ConfigurationError("首版只支持 chat_completions")
        model["timeout_seconds"] = data.get("timeout_seconds")
        model["max_output_tokens"] = data.get("max_output_tokens")
        if not isinstance(model["timeout_seconds"], (int, float)) or not 0 < model["timeout_seconds"] <= 3600:
            raise ConfigurationError("timeout_seconds 必须在 (0, 3600] 范围")
        if type(model["max_output_tokens"]) is not int or model["max_output_tokens"] <= 0:
            raise ConfigurationError("max_output_tokens 必须为正整数，需按正式料表核验容量")
        options = model.setdefault("request_options", {})
        allowed = {"stream", "temperature", "top_p"}
        if provider == "aliyun_bailian":
            allowed |= {"response_format", "enable_thinking"}
            if options.get("response_format") != {"type": "json_object"} or options.get("enable_thinking") is not False:
                raise ConfigurationError("百炼必须使用 json_object 并关闭思考")
        if set(options) - allowed or options.get("stream", False) is not False:
            raise ConfigurationError("存在未确认的供应商参数，或启用了流式响应")
        secret_names = [model["api_key_env"]]
        database = dict(data.get("database", {}))
        password_env = database.pop("password_env", "SMART_COST_DB_PASSWORD")
        secret_names.append(password_env)
        if require_secrets:
            for name in secret_names:
                if not runtime_env.get(name, "").strip():
                    raise ConfigurationError(f"缺少环境变量 {name}")
        model["api_key"] = runtime_env.get(model["api_key_env"], "")
        database["password"] = runtime_env.get(password_env, "")
        if not all(database.get(key) for key in ("host", "port", "dbname", "user")):
            raise ConfigurationError("缺少数据库连接信息")
        business = dict(data.get("business", {}))
        for key in ("quantity_task_type", "task_waiting", "task_processing", "task_completed", "task_failed"):
            if not isinstance(business.get(key), str) or not business[key].strip():
                raise ConfigurationError(f"请填写 Java 实际任务编码 {key}")
        states = [business[k] for k in ("task_waiting", "task_processing", "task_completed", "task_failed")]
        if states != ["0", "0", "1", "1"]:
            raise ConfigurationError("任务状态约定必须为等待/处理中0、成功/失败1；失败使用error_message")
        expected = {"batch_master_type": "1002", "material_file_type": "1102", "pending_file_statuses": ["2101"],
                    "include_null_status": False, "file_completed": "2102", "cbs_matched": "1401",
                    "cbs_unmatched": "1402", "cbs_method": "1501",
                    "item_types": {"SUBSECTION": "1301", "MATERIAL": "1302", "EQUIPMENT": "1303"}}
        for key, value in expected.items():
            if key in business and business[key] != value:
                raise ConfigurationError(f"{key} 与当前 Java 工程量契约不一致")
            business[key] = value
        stages = business.setdefault("task_batch_stages", [business["quantity_task_type"]])
        if (not isinstance(stages, list) or not stages or any(not isinstance(s, str) or not s.strip() or s != s.strip() for s in stages)
                or len(stages) != len(set(stages)) or business["quantity_task_type"] not in stages):
            raise ConfigurationError("task_batch_stages必须为包含目标节点的非空、不重复阶段编码数组")
        mode = data.get("task_scope_mode", "approved_only")
        if mode not in {"approved_only", "backend_queue"}:
            raise ConfigurationError("task_scope_mode 必须为 approved_only 或 backend_queue")
        scope = data.get("approved_scope", [])
        if not isinstance(scope, list) or any(not isinstance(s, dict) or set(s) != {"project_id", "batch_id"} or not all(isinstance(v, str) and v.strip() for v in s.values()) for s in scope):
            raise ConfigurationError("approved_scope 的每项必须为项目与批次 ID 对")
        if mode == "approved_only" and not scope:
            raise ConfigurationError("approved_only 模式必须填写获准的项目与批次 ID 对")
        rules_path = path.parent / data.get("classification_rules_file", "classification-rules.json")
        rules = json.loads(rules_path.read_text(encoding="utf-8-sig"))
        if not isinstance(rules, list) or any(not isinstance(r, dict) or not r.get("rule_id") or not r.get("text") for r in rules):
            raise ConfigurationError("企业规则必须为包含 rule_id 和完整 text 的数组")
        if len({r["rule_id"] for r in rules}) != len(rules):
            raise ConfigurationError("企业规则编号重复")
        from classification import compile_confirmed_rules
        try:
            compile_confirmed_rules(rules)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        poll = data.get("poll_seconds", 3)
        if not isinstance(poll, (int, float)) or poll <= 0:
            raise ConfigurationError("poll_seconds 必须为正数")
        analysis_options = data.get("analysis_options", {})
        if not isinstance(analysis_options, dict) or set(analysis_options) - {
                "chunk_rows", "estimated_output_tokens_per_row", "output_budget_ratio"}:
            raise ConfigurationError("analysis_options 包含未知配置")
        # 与分段器使用同一校验，避免启动成功后才发现输出预算不足一行。
        from chunking import plan_chunks
        # Backward-compatible parsing only; retired options cannot select behavior.
        retired = data.get("optimizations", {})
        flags = {"parse_preload", "parse_local_indexes", "parse_lossless_json",
                 "parse_compact_codec", "http_connection_pool"}
        if not isinstance(retired, dict) or set(retired) - flags - {"cbs_scope_concurrency"}:
            raise ConfigurationError("已撤除的optimizations包含未知字段或不是对象")
        for name, value in retired.items():
            valid = (type(value) is int and value == 1) if name == "cbs_scope_concurrency" else (value is False)
            if not valid:
                raise ConfigurationError("0902优化实现已撤除，旧配置不能开启：" + name)
        result = cls(model, database, business, rules, scope, path.parent / data.get("log_dir", "logs"),
                     poll, task_scope_mode=mode, analysis_options=dict(analysis_options))
        try:
            plan_chunks({"rows": [{"r": 1}]}, result)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        return result


class Trace:
    """逐文件追加 JSONL；凭据统一脱敏，不记录供应商内部思考内容。"""

    _registry_lock = threading.Lock()
    _path_locks = weakref.WeakValueDictionary()

    def __init__(self, config: Config, task: dict, file: dict):
        for value in (task["id"], file["id"]):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                raise ValueError("非法日志标识")
        self.path = config.log_dir / "quantity" / task["id"] / (file["id"] + ".jsonl")
        self.context = {k: task.get(k) for k in ("project_id", "batch_id")}
        self.context.update(task_id=task["id"], file_id=file["id"])
        self.secrets = [s for s in (config.model.get("api_key"), config.database.get("password")) if s]
        with self._registry_lock:
            key = str(self.path.resolve())
            self._write_lock = self._path_locks.setdefault(key, threading.RLock())
        self.execution_check = lambda: None

    def close(self):
        """保留逐文件生命周期接口；单次HTTPS连接在call_model内关闭。"""

    def scoped(self, **context):
        parent = self
        class ScopedTrace:
            execution_check = staticmethod(parent.execution_check)
            def write(self, event, **data):
                parent.write(event, **{**context, **data})
            def scoped(self, **extra):
                return parent.scoped(**{**context, **extra})
        return ScopedTrace()

    def write(self, event: str, **data) -> None:
        """事件时间独立于结果节点继承的任务创建时间。"""
        entry = {"time": datetime.now(timezone.utc).isoformat(), **self.context, "event": event, **data}

        def redact(value):
            if isinstance(value, str):
                for secret in self.secrets:
                    value = value.replace(secret, "[REDACTED]")
                return value
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [redact(item) for item in value]
            return value

        content = json.dumps(redact(entry), ensure_ascii=False, default=str, allow_nan=False)
        with self._write_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(content + "\n")
        logging.info("%s task=%s file=%s", event, self.context["task_id"], self.context["file_id"])
