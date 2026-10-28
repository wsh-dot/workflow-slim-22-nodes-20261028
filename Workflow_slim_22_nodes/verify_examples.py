"""Legacy business-fixture checks; missing fixtures are NOT_RUN, never passed.
No network calls, model-quality claims, or business writes.
"""
import json
import re
import hashlib
import sys
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent


def read(name):
	return json.loads((BASE / name).read_text(encoding="utf-8"))


def validate_used_schema(value, schema, path="$" ):
	"""Check the JSON Schema keywords used by this fixture, without dependencies."""
	allowed_keywords = {"type", "enum", "minimum", "minItems", "uniqueItems", "items", "properties", "required", "additionalProperties"}
	assert set(schema) <= allowed_keywords, (path, "unsupported schema keyword")
	types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
	checks = {"null": value is None, "object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str), "integer": type(value) is int}
	assert any(checks[t] for t in types), (path, "type", types)
	if "enum" in schema:
		assert value in schema["enum"], (path, "enum")
	if type(value) is int and "minimum" in schema:
		assert value >= schema["minimum"], (path, "minimum")
	if isinstance(value, dict):
		assert set(schema.get("required", [])) <= value.keys(), (path, "missing required field")
		if schema.get("additionalProperties") is False:
			assert value.keys() <= schema["properties"].keys(), (path, "extra field")
		for key, item in value.items():
			validate_used_schema(item, schema["properties"][key], path + "." + key)
	if isinstance(value, list):
		assert len(value) >= schema.get("minItems", 0), (path, "minItems")
		if schema.get("uniqueItems"):
			assert len({json.dumps(x, sort_keys=True) for x in value}) == len(value), (path, "uniqueItems")
		for index, item in enumerate(value):
			validate_used_schema(item, schema["items"], f"{path}[{index}]")


def flatten_tree(tree, parent=None):
	result = []
	for node in tree:
		assert node["parentResultKey"] == parent, "nested parent differs from parent key"
		assert isinstance(node["children"], list)
		result.append(node)
		assert [n["sortNo"] for n in node["children"]] == sorted(n["sortNo"] for n in node["children"])
		result.extend(flatten_tree(node["children"], node["resultKey"]))
	return result


def validate_leaf_consistency(candidates, evaluations):
	"""Check first-round evidence equivalence without merging any leaf IDs."""
	assert len({c["leaf_id"] for c in candidates}) == len(candidates)
	assert Counter(e["leaf_id"] for e in evaluations) == Counter(c["leaf_id"] for c in candidates)
	by_id = {e["leaf_id"]: e for e in evaluations}
	by_name = {}
	for candidate in candidates:
		name = candidate["leaf_name"].strip()
		assert name, "CBS_INPUT_INVALID: empty leaf name"
		judgment = by_id[candidate["leaf_id"]]["judgment"]
		assert judgment in {"match", "possible", "no_match"}
		assert by_name.setdefault(name, judgment) == judgment, "CBS_OUTPUT_INCONSISTENT"


def verify_cbs(request, leaf_input, leaf_output, parent_input, parent_output, response):
	file = request["files"][0]
	cbs = {n["cbsNodeId"]: n for n in request["cbsNodes"]}
	assert len(cbs) == len(request["cbsNodes"])
	leaves = {k: n for k, n in cbs.items() if n["isUnitProject"] and not any(x["parentCbsNodeId"] == k for x in cbs.values())}
	assert Counter(c["leaf_id"] for c in leaf_input["candidates"]) == Counter(leaves.keys())
	for c in leaf_input["candidates"]:
		assert c == {"leaf_id": c["leaf_id"], "leaf_name": leaves[c["leaf_id"]]["name"]}
	context = {k: file[k] for k in ("header", "internalSections", "parseWarnings", "coverage")}
	context_id = hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
	valid_refs = {"header." + key for key in file["header"]} | {"internalSections." + s["sectionId"] + ".title" for s in file["internalSections"]} | {"coverage", "parseWarnings"}
	for section in file["internalSections"]:
		assert set(section["sourceRawItemIds"]) <= {r["rawItemId"] for r in file["rawItems"]}
	for packet in (leaf_input, parent_input):
		assert packet["file_id"] == file["fileId"]
		assert packet["cbs_revision"] == request["cbsRevision"]
		assert packet["match_context"] == context, "two rounds must use the original full context"
		assert packet["context_id"] == context_id
	for output, schema_name in ((leaf_output, "cbs-leaf-output.schema.json"), (parent_output, "cbs-parent-output.schema.json")):
		validate_used_schema(output, read(schema_name))
		assert output["context_id"] == context_id
		for evaluation in output["evaluations"]:
			assert set(evaluation["evidence_refs"]) <= valid_refs
	assert Counter(e["leaf_id"] for e in leaf_output["evaluations"]) == Counter(leaves.keys())
	validate_leaf_consistency(leaf_input["candidates"], leaf_output["evaluations"])
	first = {e["leaf_id"]: e for e in leaf_output["evaluations"]}
	retained = {key for key, e in first.items() if e["judgment"] != "no_match"}
	assert Counter(c["leaf_id"] for c in parent_input["candidates"]) == Counter(retained)
	for c in parent_input["candidates"]:
		leaf = leaves[c["leaf_id"]]
		assert c["leaf_name"] == leaf["name"]
		assert c["parent_id"] == leaf["parentCbsNodeId"]
		assert c["parent_name"] == cbs[c["parent_id"]]["name"]
		assert c["leaf_judgment"] == first[c["leaf_id"]]["judgment"]
	assert Counter(e["leaf_id"] for e in parent_output["evaluations"]) == Counter(retained)
	parent_judgments = {}
	for e in parent_output["evaluations"]:
		assert e["parent_id"] == leaves[e["leaf_id"]]["parentCbsNodeId"]
		assert parent_judgments.setdefault(e["parent_id"], e["judgment"]) == e["judgment"]
	positives = [e["leaf_id"] for e in parent_output["evaluations"] if e["judgment"] == "match"]
	uncertain = any(e["judgment"] == "possible" for e in parent_output["evaluations"])
	ready = leaf_output["context_status"] == parent_output["context_status"] == "sufficient"
	accepted = len(positives) == 1 and not uncertain and ready and first[positives[0]]["judgment"] == "match"
	match = response["data"]["cbsMatch"]
	assert "cbsAssignments" not in response["data"]
	assert match["scope"] == "FILE" and match["contextId"] == context_id
	assert match["executionStatus"] == "SUCCEEDED"
	assert set(match["evidenceRefs"]) <= valid_refs
	assert Counter(match["stageOne"]["candidateLeafIds"]) == Counter(retained)
	assert match["stageOne"]["executionStatus"] == "SUCCEEDED"
	assert Counter(match["stageTwo"]["evaluatedLeafIds"]) == Counter(retained)
	assert match["stageTwo"]["executionStatus"] == ("SUCCEEDED" if retained else "SKIPPED")
	assert match["cbsMatchStatus"] == ("1" if accepted else "0")
	if accepted:
		assert match["projectCbsId"] == positives[0]
		assert match["parentCbsNodeId"] == leaves[positives[0]]["parentCbsNodeId"]
		assert match["reasonCode"] == "MATCHED"
	else:
		assert match["projectCbsId"] is None and match["parentCbsNodeId"] is None
		assert match["reasonCode"] != "MATCHED"
	assert len(flatten_tree(response["data"]["tree"])) == response["data"]["coverage"]["outputNodeCount"]
	return retained


def must_reject(label, args):
	try:
		verify_cbs(*args)
	except AssertionError:
		return label
	raise AssertionError("invalid CBS fixture accepted: " + label)


def main():
	# Fixtures are synthetic examples restored from the original local proposal.
	required = ["build-request", "model-input", "model-output", "build-result", "project-node-case", "build-request-unmatched", "build-result-unmatched"]
	required += [stem + suffix for stem in ("cbs-leaf-input", "cbs-leaf-output", "cbs-parent-input", "cbs-parent-output") for suffix in ("", "-unmatched")]
	missing = ["examples/" + name + ".json" for name in required if not (BASE / "examples" / (name + ".json")).is_file()]
	if missing:
		print(json.dumps({"status": "NOT_RUN", "scope": "legacy_synthetic_business_fixtures_only", "reason": "Original examples were not supplied", "missing": missing, "live_workflow_test": "NOT_RUN"}, ensure_ascii=False, indent=2))
		return 2
	request = read("examples/build-request.json")
	model_input = read("examples/model-input.json")
	model_output = read("examples/model-output.json")
	response = read("examples/build-result.json")
	schema = read("model-output.schema.json")
	validate_used_schema(model_output, schema)
	file = request["files"][0]
	raw_rows = file["rawItems"]
	raw_by_id = {row["rawItemId"]: row for row in raw_rows}
	assert len(raw_by_id) == len(raw_rows)
	assert len({row["orderNo"] for row in raw_rows}) == len(raw_rows)
	assert response["requestId"] == request["requestId"]
	assert model_output["packet_id"] == model_input["packet_id"]
	assert [r["r"] for r in model_output["rows"]] == [r["r"] for r in model_input["rows"]]
	rmap = {i: row for i, row in enumerate(raw_rows, 1)}
	model_rows = {r["r"]: r for r in model_output["rows"]}
	rule_ids = {r["rule_id"] for r in model_input["classification_rules"]["rules"]}
	for row in model_output["rows"]:
		refs = [row[k] for k in ("parent", "qty_from", "unit_from", "quantity_parent", "quantity_basis_ref")]
		refs += row["inherit"] + row["classification"]["source_rows"]
		assert all(ref in rmap for ref in refs if ref is not None)
		assert set(row["classification"]["rule_ids"]) <= rule_ids
		ancestors = []
		current = row["parent"]
		while current is not None:
			assert current != row["r"] and current not in ancestors
			ancestors.append(current)
			current = model_rows[current]["parent"]
		assert set(row["inherit"]) <= set(ancestors)
		if row["quantity_basis"] == "per_parent":
			assert row["quantity_parent"] in ancestors
		else:
			assert row["quantity_parent"] is None
		if row["role"] in ("item", "assembly", "component"):
			assert row["classification"]["status"] != "not_applicable"
		else:
			assert row["node_type"] is None
	data = response["data"]
	for field in ("fileId", "fileRevision", "buildGeneration"):
		assert data[field] == file[field]
	for field in ("cbsRevision", "classificationRuleVersion"):
		assert data[field] == request[field]
	flat_nodes = flatten_tree(data["tree"])
	nodes = {n["resultKey"]: n for n in flat_nodes}
	assert len(nodes) == len(flat_nodes)
	sibling_order = set()
	for node in nodes.values():
		assert node["fileId"] == file["fileId"]
		assert set(node["sourceRawItemIds"]) <= raw_by_id.keys()
		assert node["parentResultKey"] is None or node["parentResultKey"] in nodes
		order_key = (node["parentResultKey"], node["sortNo"])
		assert order_key not in sibling_order
		sibling_order.add(order_key)
		seen = {node["resultKey"]}
		current = node["parentResultKey"]
		while current is not None:
			assert current not in seen
			seen.add(current)
			current = nodes[current]["parentResultKey"]
		for sources in node["fieldSources"].values():
			for source in sources:
				raw = raw_by_id[source["rawItemId"]]
				assert source["field"] in raw
				assert set(source["cellIds"]) <= {cell["cellId"] for cell in raw["rawCells"]}
		if node["type"] in ("PROJECT", "SUBSECTION"):
			assert node["quantity"] is None
		if node["quantityBasis"] == "PER_PARENT":
			parent = nodes[node["quantityParentResultKey"]]
			assert Decimal(node["quantity"]) == Decimal(node["sourceQuantity"]) * Decimal(parent["quantity"])
	dispositions = data["rowDispositions"]
	assert Counter(r["rawItemId"] for r in dispositions) == Counter(raw_by_id.keys())
	assert all(set(r["resultKeys"]) <= nodes.keys() for r in dispositions)
	assert data["coverage"]["inputRowCount"] == len(raw_rows)
	assert data["coverage"]["accountedRowCount"] == len(dispositions)
	assert data["coverage"]["outputNodeCount"] == len(nodes)
	assert len(raw_rows) == 11 and len(nodes) == 9
	assert sum(Decimal(n["quantity"]) for n in nodes.values() if n["name"] == "箱变 华变" and n["quantity"] is not None) == Decimal("2")
	assert len([n for n in nodes.values() if n["name"] == "电力电缆" and n["type"] == "MATERIAL"]) == 2
	matched = [request] + [read("examples/" + name + ".json") for name in ("cbs-leaf-input", "cbs-leaf-output", "cbs-parent-input", "cbs-parent-output")] + [response]
	unmatched = [read("examples/build-request-unmatched.json")] + [read("examples/" + name + "-unmatched.json") for name in ("cbs-leaf-input", "cbs-leaf-output", "cbs-parent-input", "cbs-parent-output")] + [read("examples/build-result-unmatched.json")]
	for args in (matched, unmatched):
		verify_cbs(*args)
	assert unmatched[-1]["data"]["tree"] == response["data"]["tree"], "unmatched file must retain the whole tree"
	assert unmatched[-1]["data"]["semanticStatus"] == "REVIEW"
	negative_checks = []
	bad = deepcopy(matched)
	bad[3]["match_context"] = {"header": {"siteName": file["header"]["siteName"]}}
	negative_checks.append(must_reject("reject_reduced_round_two_context", bad))
	bad = deepcopy(matched)
	excluded = next(e["leaf_id"] for e in bad[2]["evaluations"] if e["judgment"] == "no_match")
	bad[3]["candidates"][0]["leaf_id"] = excluded
	negative_checks.append(must_reject("reject_round_two_outside_candidates", bad))
	bad = deepcopy(matched)
	bad[4]["evaluations"][0]["parent_id"] = bad[4]["evaluations"][1]["parent_id"]
	negative_checks.append(must_reject("reject_wrong_direct_parent", bad))
	bad = deepcopy(matched)
	bad[-1]["data"]["cbsMatch"]["projectCbsId"] = bad[-1]["data"]["cbsMatch"]["parentCbsNodeId"]
	negative_checks.append(must_reject("reject_parent_as_final_target", bad))
	ambiguous = deepcopy(matched)
	first_parent = ambiguous[3]["candidates"][0]
	second_leaf = ambiguous[3]["candidates"][1]["leaf_id"]
	next(n for n in ambiguous[0]["cbsNodes"] if n["cbsNodeId"] == second_leaf)["parentCbsNodeId"] = first_parent["parent_id"]
	ambiguous[3]["candidates"][1].update({"parent_id": first_parent["parent_id"], "parent_name": first_parent["parent_name"]})
	ambiguous[4]["evaluations"][1].update({"parent_id": first_parent["parent_id"], "judgment": "match"})
	negative_checks.append(must_reject("reject_first_leaf_when_same_parent_is_ambiguous", ambiguous))
	ambiguous[-1]["data"]["cbsMatch"].update({"cbsMatchStatus": "0", "projectCbsId": None, "parentCbsNodeId": None, "reasonCode": "AMBIGUOUS"})
	verify_cbs(*ambiguous)
	# Regression: identical leaves under the same parent cannot become unique
	# merely because the first round arbitrarily excludes one of them.
	false_unique = deepcopy(ambiguous)
	next(e for e in false_unique[2]["evaluations"] if e["leaf_id"] == second_leaf)["judgment"] = "no_match"
	false_unique[3]["candidates"] = [c for c in false_unique[3]["candidates"] if c["leaf_id"] != second_leaf]
	false_unique[4]["evaluations"] = [e for e in false_unique[4]["evaluations"] if e["leaf_id"] != second_leaf]
	false_unique[-1]["data"]["cbsMatch"] = deepcopy(matched[-1]["data"]["cbsMatch"])
	false_unique[-1]["data"]["cbsMatch"]["stageOne"]["candidateLeafIds"] = [first_parent["leaf_id"]]
	false_unique[-1]["data"]["cbsMatch"]["stageTwo"]["evaluatedLeafIds"] = [first_parent["leaf_id"]]
	negative_checks.append(must_reject("reject_false_unique_after_same_name_exclusion", false_unique))
	project_case = read("examples/project-node-case.json")
	validate_used_schema(project_case["modelOutput"], schema)
	project_rows = project_case["rawItems"]
	project_nodes = flatten_tree(project_case["tree"])
	assert len(project_rows) == len(project_nodes) == 4
	assert [n["type"] for n in project_nodes] == ["PROJECT", "SUBSECTION", "SUBSECTION", "EQUIPMENT"]
	assert [n["semanticRole"] for n in project_nodes] == [r["role"] for r in project_case["modelOutput"]["rows"]]
	assert project_nodes[0]["quantity"] is None
	assert "1.90216MWp" in project_nodes[0]["name"]
	assert project_nodes[-1]["quantity"] == "3068"
	project_rule_ids = {r["rule_id"] for r in project_case["classificationRules"]["rules"]}
	for i, (raw, model_row, node) in enumerate(zip(project_rows, project_case["modelOutput"]["rows"], project_nodes), 1):
		assert model_row["r"] == i and model_row["parent"] == (i - 1 if i > 1 else None)
		assert node["sourceRawItemIds"] == [raw["rawItemId"]]
		assert set(model_row["classification"]["rule_ids"]) <= project_rule_ids
		assert not model_row["inherit"] and model_row["quantity_parent"] is None
		if node["type"] in ("PROJECT", "SUBSECTION"):
			assert model_row["node_type"] is None
			assert model_row["quantity_basis"] == "not_applicable"
			assert node["quantityBasis"] == node["quantityStatus"] == "NOT_APPLICABLE"
			assert node["quantity"] is None and not node["classification"]["ruleIds"]
		for sources in node["fieldSources"].values():
			for source in sources:
				assert source["rawItemId"] == raw["rawItemId"]
				assert source["field"] in raw
				assert set(source["cellIds"]) <= {c["cellId"] for c in raw["rawCells"]}
	# The former external D-drive DSL and 57-node assertions do not apply to this revision.
	from verify_simplified import verify
	static_result = verify(BASE)
	result = {"status": "PASSED", "scope": "synthetic documentation fixtures and static proposal inventory only", "input_rows": len(raw_rows), "output_nodes": len(nodes), "project_case_nodes": len(project_nodes), "workflow_target_nodes": static_result["core_nodes"], "local_links_checked": static_result["local_links_checked"], "cbs_valid_cases": 3, "negative_cbs_checks": negative_checks, "live_workflow_test": "NOT_RUN", "provider_model_test": "NOT_RUN", "limitations": "Partial local fixture assertions, including the first-round consistency regression; not service execution, all quantity semantics, or real model quality."}
	print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
	sys.exit(main() or 0)
