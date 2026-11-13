"""正式入口：轮询 Java 已创建的工程量任务，依次提交每份料表。"""
from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import signal
import threading

import psycopg
from psycopg.rows import dict_row

from ai_service import AnalysisError, analyze_material_file, build_file_result
from analysis_snapshot import build_snapshot
from config import Config, Trace
from repository import Repository


def process_task(task: dict, config: Config, repository: Repository) -> bool:
    """成功空查询后才完成任务；任何文件异常保留先前提交结果并标记任务失败。"""
    b = config.business
    if not repository.set_task_status(task, b["task_processing"]):
        logging.info("task_claim_skipped task=%s", task["id"])
        return False
    completed_files = 0
    trace = None
    try:
        cbs = repository.load_cbs(task["project_id"])
        repository.freeze_execution(task, cbs)
        while True:
            file = repository.find_next_file(task["batch_id"])
            if file is None:
                if not repository.set_task_status(task, b["task_completed"]):
                    raise RuntimeError("任务状态已变化，无法确认完成")
                logging.info("task_completed task=%s files=%s reason=no_pending_files", task["id"], completed_files)
                return True
            if trace is not None:
                trace.close()
            trace = Trace(config, task, file)
            trace.execution_check = repository.check_execution
            repository.check_execution()
            trace.write('execution_profile', protocol='0902-full-object-v1',
                        execution=getattr(repository, '_execution', None))
            trace.write("file_started", file=file, completed_files=completed_files)
            input_context = repository.load_file_input(file)
            header, raw_rows = input_context["header"], input_context["raw_rows"]
            trace.write("file_input_loaded", header=header, raw_rows=raw_rows, cbs_nodes=cbs)
            analysis = analyze_material_file(header, raw_rows, cbs, config, trace)
            built = build_file_result(file, analysis, task, config, trace)
            items = built.items
            snapshot = build_snapshot(file, input_context, analysis, built, task, config)
            repository.save_file_result(file, items, task, trace, snapshot)
            completed_files += 1
            trace.write("file_completed", item_count=len(items), completed_files=completed_files)
    except Exception as exc:
        # 简短错误不包含供应商正文、SQL 或凭据；详细证据保留在当前文件诊断中。
        file_hint = f"料表“{str(file.get('original_name') or file['id'])[:100]}”：" if trace else ""
        summary = f"{file_hint}工程量处理失败（{type(exc).__name__}），请重试未完成料表。"
        # 仅展示程序生成的简短结构错误，不把模型正文、SQL或网络异常原文发给界面。
        if trace and isinstance(exc, AnalysisError) and exc.public_message:
            summary = (f"料表“{str(file.get('original_name') or file['id'])[:100]}”：{exc.public_message}")[:180]
        logging.error("task_failed task=%s files=%s error_type=%s", task["id"], completed_files, type(exc).__name__)
        if trace:
            try:
                trace.write("file_failed", error_type=type(exc).__name__, error_message=str(exc), completed_files=completed_files)
            except Exception as log_exc:
                logging.error("failure_trace_unavailable task=%s error_type=%s", task["id"], type(log_exc).__name__)
        # 状态写入失败继续向上报告，不能当作任务已结束后静默轮询。
        if not repository.set_task_status(task, b["task_failed"], summary):
            raise RuntimeError("失败状态未更新，请核对任务状态") from exc
        return False
    finally:
        if trace is not None:
            trace.close()
        repository.release_task(task)


def run_runner(config: Config, repository: Repository, *, once: bool = False, stop_event=None) -> None:
    """单进程顺序执行；查询错误终止运行，停止请求在当前任务结束后生效。"""
    stop_event = stop_event or threading.Event()
    logging.info("runner_started provider=%s model=%s task_type=%s scope_mode=%s scope=%s poll=%s",
                 config.model["provider"], config.model["model"], config.business["quantity_task_type"],
                 config.task_scope_mode, config.approved_scope, config.poll_seconds)
    try:
        while not stop_event.is_set():
            task = repository.find_waiting_task()
            if task is not None:
                success = process_task(task, config, repository)
                if once and not success:
                    raise RuntimeError("本轮任务处理失败，详见任务状态和诊断日志")
            if once:
                return
            if task is None:
                stop_event.wait(config.poll_seconds)
    finally:
        logging.info("runner_stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="smartCost 工程量编制 AI Runner")
    parser.add_argument("--config", default="config.application.local.json",
                        help="运行配置，默认config.application.local.json（正常应用队列）")
    parser.add_argument("--once", action="store_true", help="最多读取并处理一条获准任务")
    parser.add_argument("--check-config", action="store_true", help="只检查配置，不连接数据库或模型，也不检查凭据值")
    args = parser.parse_args()
    try:
        cfg = Config.load(args.config, require_secrets=not args.check_config)
        if args.check_config:
            print("配置检查通过；未连接数据库、未调用模型。")
            raise SystemExit(0)
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                            handlers=[logging.StreamHandler(), RotatingFileHandler(cfg.log_dir / "runner.log",
                                      maxBytes=10_000_000, backupCount=5, encoding="utf-8")])
        stop = threading.Event()

        def request_stop(signum, frame):
            """完成当前任务后退出，避免供应商切换发生在一条任务中间。"""
            logging.info("stop_requested signal=%s; waiting for current task", signum)
            stop.set()

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
        with psycopg.connect(**cfg.database, autocommit=True, row_factory=dict_row) as connection:
            run_runner(cfg, Repository(connection, cfg), once=args.once, stop_event=stop)
    except Exception as exc:
        # 不打印连接异常原文，防止运行环境中的凭据被驱动异常带入控制台。
        logging.error("Runner 启动或运行失败：%s", type(exc).__name__)
        if isinstance(exc, (ValueError, FileNotFoundError)):
            logging.error("%s", exc)
        raise SystemExit(1)
