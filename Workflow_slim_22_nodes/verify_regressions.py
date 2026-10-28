"""Local contract regression examples, not a deployed service implementation."""
import argparse
import json
from copy import deepcopy
from pathlib import Path

from verify_examples import validate_leaf_consistency

BASE = Path(__file__).resolve().parent


def read(name):
	return json.loads((BASE / "examples" / name).read_text(encoding="utf-8"))


def require(value, reason):
	if not value:
		raise ValueError(reason)


def validate_runtime_contract(case):
	"""Validate recorded call examples against their frozen execution config."""
	frozen, run = case["frozen_config"], case["run"]
	start, headers, stop = case["start_request"], case["claim_headers"], case["stop_request"]
	for key in ("execution_config_id", "workflow_id", "dify_app_id", "dify_api_base", "credential_ref"):
		require(run.get(key) == frozen.get(key) and bool(frozen.get(key)), "EXECUTION_VERSION_MISMATCH")
	require(run.get("observed_workflow_id") == frozen["workflow_id"], "EXECUTION_VERSION_MISMATCH")
	require(bool(run.get("workflow_run_id")) and bool(run.get("dify_user")), "MISSING_RUN_IDENTITY")
	base = frozen["dify_api_base"]
	if frozen["pin_mode"] == "WORKFLOW_ID":
		expected_url = base + "/workflows/" + frozen["workflow_id"] + "/run"
	elif frozen["pin_mode"] == "IMMUTABLE_APP":
		require(case.get("app_release_frozen") is True, "APP_RELEASE_NOT_FROZEN")
		expected_url = base + "/workflows/run"
	else:
		raise ValueError("UNKNOWN_PIN_MODE")
	require(start.get("method") == "POST" and start.get("url") == expected_url, "WRONG_VERSION_ROUTE")
	require(start.get("credential_ref") == frozen["credential_ref"], "WRONG_APP_CREDENTIAL")
	require(start.get("body") == {
		"inputs": {"dispatch_id": run["dispatch_id"]},
		"response_mode": "streaming", "user": run["dify_user"],
	}, "INVALID_START_BODY")
	for key, expected in {
		"X-Quantity-Dispatch-Id": run["dispatch_id"],
		"X-Quantity-Run-Id": run["workflow_run_id"],
		"X-Quantity-Workflow-Id": frozen["workflow_id"],
		"X-Quantity-Execution-Config-Id": frozen["execution_config_id"],
	}.items():
		require(headers.get(key) == expected, "INVALID_CLAIM_IDENTITY")
	if stop is not None:
		require(bool(run.get("task_id")), "TASK_ID_UNAVAILABLE")
		require(stop.get("method") == "POST" and stop.get("url") == base + "/workflows/tasks/" + run["task_id"] + "/stop", "WRONG_STOP_TASK")
		require(stop.get("body") == {"user": run["dify_user"]}, "WRONG_STOP_USER")
		require(stop.get("credential_ref") == frozen["credential_ref"], "WRONG_STOP_CREDENTIAL")
	if case.get("release_run_slot"):
		require(run.get("run_terminal_confirmed") is True, "RUN_NOT_CONFIRMED_TERMINAL")
	if case.get("release_model_budget"):
		require(run.get("model_termination_confirmed") is True, "MODEL_NOT_CONFIRMED_TERMINAL")


def verify():
	passed = []
	def accept(name, action):
		action()
		passed.append(name)
	def reject(name, action, error):
		try:
			action()
		except (AssertionError, ValueError) as exc:
			require(error in str(exc), "Unexpected rejection for " + name + ": " + str(exc))
			passed.append(name)
			return
		raise ValueError("Invalid example accepted: " + name)

	leaf = read("cbs-leaf-input.json")
	output = read("cbs-leaf-output.json")
	accept("same_name_both_retained", lambda: validate_leaf_consistency(leaf["candidates"], output["evaluations"]))
	for value in ("possible", "no_match"):
		bad = deepcopy(output)
		bad["evaluations"][-1]["judgment"] = value
		reject("same_name_match_versus_" + value, lambda: validate_leaf_consistency(leaf["candidates"], bad["evaluations"]), "CBS_OUTPUT_INCONSISTENT")
	bad = deepcopy(leaf)
	bad["candidates"][-1]["leaf_name"] = "  电气部分  "
	conflict = read("cbs-leaf-output-inconsistent.json")
	reject("same_name_whitespace_conflict", lambda: validate_leaf_consistency(bad["candidates"], conflict["evaluations"]), "CBS_OUTPUT_INCONSISTENT")
	accept("candidate_order_independent", lambda: validate_leaf_consistency(list(reversed(leaf["candidates"])), output["evaluations"]))

	baseline = read("build-result.json")["data"]
	failed = read("build-result-cbs-inconsistent.json")["data"]
	def check_unattached_result():
		require(failed["tree"] == baseline["tree"] and failed["rowDispositions"] == baseline["rowDispositions"], "TREE_OR_PROVENANCE_LOST")
		require(failed["executionStatus"] == "SUCCEEDED", "FILE_INCORRECTLY_FAILED")
		require(failed["semanticStatus"] == baseline["semanticStatus"] == "READY", "CBS_MUST_NOT_FORCE_REVIEW")
		match = failed["cbsMatch"]
		require(match["cbsMatchStatus"] == "0" and match["projectCbsId"] is None and match["parentCbsNodeId"] is None, "FALSE_ATTACHMENT")
		require(match["executionStatus"] == "FAILED" and match["reasonCode"] == "CBS_OUTPUT_INCONSISTENT", "DIAGNOSTIC_LOST")
		require(match["stageOne"] == {"executionStatus": "FAILED", "candidateLeafIds": []}, "INVALID_LEAF_CHECKPOINT")
		require(match["stageTwo"] == {"executionStatus": "SKIPPED", "evaluatedLeafIds": []}, "PARENT_MUST_BE_SKIPPED")
	accept("conflict_preserves_ready_tree_as_unattached", check_unattached_result)

	case = read("runtime-contract.json")
	accept("pinned_version_and_stop_identity", lambda: validate_runtime_contract(case))
	def mutate(name, edit, error):
		bad = deepcopy(case)
		edit(bad)
		reject(name, lambda: validate_runtime_contract(bad), error)
	mutate("reject_run_id_as_task_id", lambda c: c["stop_request"].update(url=c["frozen_config"]["dify_api_base"] + "/workflows/tasks/" + c["run"]["workflow_run_id"] + "/stop"), "WRONG_STOP_TASK")
	mutate("reject_wrong_stop_user", lambda c: c["stop_request"].update(body={"user": "another-user"}), "WRONG_STOP_USER")
	mutate("reject_stop_without_task_id", lambda c: c["run"].update(task_id=None), "TASK_ID_UNAVAILABLE")
	mutate("reject_latest_version_fallback", lambda c: c["start_request"].update(url=c["frozen_config"]["dify_api_base"] + "/workflows/run"), "WRONG_VERSION_ROUTE")
	mutate("reject_changed_observed_version", lambda c: c["run"].update(observed_workflow_id="new-published-version"), "EXECUTION_VERSION_MISMATCH")
	mutate("reject_changed_execution_config", lambda c: c["run"].update(execution_config_id="new-config"), "EXECUTION_VERSION_MISMATCH")
	mutate("reject_changed_claim_version", lambda c: c["claim_headers"].update({"X-Quantity-Workflow-Id": "wrong-version"}), "INVALID_CLAIM_IDENTITY")
	mutate("reject_blocking_mode", lambda c: c["start_request"]["body"].update(response_mode="blocking"), "INVALID_START_BODY")
	mutate("stop_ack_does_not_release_run_slot", lambda c: c.update(release_run_slot=True), "RUN_NOT_CONFIRMED_TERMINAL")
	mutate("stop_ack_does_not_release_model_budget", lambda c: c.update(release_model_budget=True), "MODEL_NOT_CONFIRMED_TERMINAL")
	pending = deepcopy(case)
	pending["run"]["task_id"] = None
	pending["stop_request"] = None
	accept("claim_before_task_id_arrival", lambda: validate_runtime_contract(pending))
	repair = deepcopy(case)
	repair["run"].update(dispatch_id="repair-dispatch", workflow_run_id="repair-run", task_id=None)
	repair["start_request"]["body"]["inputs"]["dispatch_id"] = "repair-dispatch"
	repair["claim_headers"].update({"X-Quantity-Dispatch-Id": "repair-dispatch", "X-Quantity-Run-Id": "repair-run"})
	repair["stop_request"] = None
	accept("repair_keeps_original_execution_version", lambda: validate_runtime_contract(repair))
	legacy = deepcopy(case)
	legacy["frozen_config"]["pin_mode"] = "IMMUTABLE_APP"
	legacy["app_release_frozen"] = True
	legacy["start_request"]["url"] = legacy["frozen_config"]["dify_api_base"] + "/workflows/run"
	accept("immutable_app_compatibility", lambda: validate_runtime_contract(legacy))
	legacy["app_release_frozen"] = False
	reject("reject_mutable_compatibility_app", lambda: validate_runtime_contract(legacy), "APP_RELEASE_NOT_FROZEN")
	return {
		"status": "PASSED", "scope": "local_contract_regression_examples_only",
		"checks": passed, "check_count": len(passed),
		"live_workflow_test": "NOT_RUN", "java_integration_test": "NOT_RUN",
		"limitations": "Validates local examples and contract predicates; does not implement or test production scheduling, cancellation, version pinning, or models.",
	}


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--write-report", action="store_true")
	args = parser.parse_args()
	result = verify()
	text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
	if args.write_report:
		(BASE / "regression_validation.json").write_text(text, encoding="utf-8")
	print(text)
