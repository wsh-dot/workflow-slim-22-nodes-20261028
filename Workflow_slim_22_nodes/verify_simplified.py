"""Static proposal checks only; no Dify, provider, Java or business-fixture calls."""
import hashlib
import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def verify(base=BASE):
    base = Path(base)
    inventory = json.loads((base / "workflow-node-inventory.json").read_text(encoding="utf-8"))
    nodes = inventory["nodes"]
    ids = {n["id"] for n in nodes}
    check(len(ids) == len(nodes) == inventory["target_core_node_count"] == 22, "Core node count or uniqueness")
    check(Counter(n["type"] for n in nodes) == {
        "start": 1, "end": 1, "llm": 3, "http-request": 6, "code": 6, "if-else": 5
    }, "Core node type counts")
    old_ids = [n["id"] for n in inventory["source_proposal_nodes"]]
    migration = inventory["migration_from_57"]
    check(len(set(old_ids)) == len(old_ids) == 57, "Original proposal inventory")
    check(Counter(x["old_id"] for x in migration) == Counter(old_ids), "Every original node needs exactly one migration action")
    optional = inventory["optional_serializers"]
    optional_ids = {n["id"] for n in optional}
    check(len(optional_ids) == len(optional) == 3 and not optional_ids & ids, "Optional serializer identities")
    for row in migration:
        check(bool(row["action"] and row["responsibility_owner"] and row["reason"]), "Missing migration responsibility")
        check(set(row["target_ids"]) <= ids | optional_ids, "Migration points to absent target")

    edges = inventory["normal_and_business_branch_edges"]
    check(len(edges) == 28, "Business edge count")
    check(len({(e["from"], e["to"], e["condition"]) for e in edges}) == len(edges), "Duplicate business edge")
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in edges:
        check(edge["from"] in ids and edge["to"] in ids, "Edge endpoint is missing")
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    check(not incoming["qStart"] and not outgoing["qEnd"], "Start/End direction")

    visited, active = set(), set()
    def walk(node):
        check(node not in active, "Workflow graph contains a cycle")
        if node in visited:
            return
        active.add(node)
        for edge in outgoing[node]:
            walk(edge["to"])
        active.remove(node)
        visited.add(node)
    walk("qStart")
    check(visited == ids, "Unreachable node")
    check({node for node in ids if not outgoing[node]} == {"qEnd"}, "Non-End dead end")

    expected_routes = {
        "qResumeGate": {"STRUCTURE_INITIAL": "sLLM", "STRUCTURE_REPAIR": "sLLM", "CBS_LEAF": "qPrepareLeaf", "CBS_PARENT": "qPrepareParent", "RETURN": "qEnd"},
        "sStructureGate": {"CBS_LEAF": "qPrepareLeaf", "RETURN": "qEnd"},
        "qLeafInputGate": {"RUN_LEAF": "qCbsLeafLLM", "RETURN": "qEnd"},
        "qCbsCandidateGate": {"CBS_PARENT": "qPrepareParent", "RETURN": "qEnd"},
        "qParentInputGate": {"RUN_PARENT": "qCbsParentLLM", "RETURN": "qEnd"},
    }
    for node in nodes:
        node_id = node["id"]
        if node["type"] == "if-else":
            routes = {}
            for edge in outgoing[node_id]:
                for action in edge["condition"].split(" or "):
                    check(action not in routes, "Ambiguous route")
                    routes[action] = edge["to"]
            check(routes == expected_routes[node_id], "Missing or changed business route: " + node_id)
        elif node_id != "qEnd":
            check(len(outgoing[node_id]) == 1, "Unexpected non-gate branch: " + node_id)

    gate_ids = list(expected_routes)
    paths = set()
    for choices in itertools.product(*(list(expected_routes[g]) for g in gate_ids)):
        selected = dict(zip(gate_ids, choices))
        node, path = "qStart", []
        while node != "qEnd":
            path.append(node)
            node = expected_routes[node][selected[node]] if node in expected_routes else outgoing[node][0]["to"]
        path.append("qEnd")
        paths.add(tuple(path))
        model_nodes = [n for n in path if n in {"sLLM", "qCbsLeafLLM", "qCbsParentLLM"}]
        phase = selected["qResumeGate"]
        if phase == "CBS_PARENT":
            check(set(model_nodes) <= {"qCbsParentLLM"}, "Parent resume repeats a completed model stage")
        if phase == "CBS_LEAF":
            check("sLLM" not in model_nodes, "Leaf resume repeats structure model")
        if phase == "RETURN":
            check(not model_nodes, "RETURN invokes model")
        check(path.index("qReadRunState") < path.index("qEnd"), "End lacks common identity source")
    for serializer in optional:
        check(serializer["before"] in ids, "Serializer target is absent")
        sources = incoming[serializer["before"]]
        check(len(sources) == 1 and sources[0]["from"] in {"sLLM", "qCbsLeafLLM", "qCbsParentLLM"}, "Serializer is not between model and submission")
    check(len(ids | optional_ids) == inventory["target_object_only_compatibility_node_count"] == 25, "Compatibility count")

    rules = inventory["runtime_rules"]
    for name in ("same_name_leaf_judgment_consistency", "cbs_unattached_does_not_force_review", "freeze_execution_config_across_runs", "stop_ack_is_not_terminal", "old_dispatch_late_writes_rejected"):
        check(rules.get(name) is True, "Missing runtime contract: " + name)
    check(rules.get("response_mode") == "streaming", "Streaming mode required")
    check(set(rules.get("version_pin_modes", [])) == {"WORKFLOW_ID", "IMMUTABLE_APP"}, "Version pinning modes")
    check(set(inventory["runtime_identity_fields"]) >= {"dispatch_id", "workflow_run_id", "task_id", "workflow_id", "observed_workflow_id", "execution_config_id", "dify_user", "dify_app_id", "credential_ref"}, "Runtime identity contract incomplete")
    check(set(inventory["internal_http_headers"]) >= {"X-Quantity-Dispatch-Id", "X-Quantity-Run-Id", "X-Quantity-Workflow-Id", "X-Quantity-Execution-Config-Id"}, "Version headers missing")

    config = (base / "07-Workflow逐节点配置参考.md").read_text(encoding="utf-8")
    for node_id in ids | optional_ids:
        check("`" + node_id + "`" in config, "Missing configuration: " + node_id)
    link_count = 0
    for document in base.glob("*.md"):
        text = document.read_text(encoding="utf-8")
        check(text.count("```") % 2 == 0, "Unclosed code fence: " + document.name)
        for target in re.findall(r"\]\(([^\n)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            local = target.strip("<>").split("#", 1)[0]
            check((document.parent / local).exists(), "Missing local link: " + document.name + " -> " + target)
            link_count += 1
    schemas = {}
    for name in ("model-output.schema.json", "cbs-leaf-output.schema.json", "cbs-parent-output.schema.json"):
        raw = (base / name).read_bytes()
        json.loads(raw)
        schemas[name] = hashlib.sha256(raw).hexdigest()
    return {
        "status": "PASSED",
        "scope": "static_documentation_and_configuration_only",
        "core_nodes": len(ids), "optional_serializers": len(optional),
        "compatibility_max_nodes": 25, "business_edges": len(edges),
        "original_nodes_accounted_for": len(migration),
        "distinct_static_paths_checked": len(paths), "local_links_checked": link_count,
        "schema_sha256": schemas,
        "live_workflow_test": "NOT_RUN",
        "provider_model_test": "NOT_RUN",
        "java_integration_test": "NOT_RUN",
        "business_fixture_test": "NOT_RUN_BY_THIS_SCRIPT_use_verify_examples.py",
        "contract_regression_test": "NOT_RUN_BY_THIS_SCRIPT_use_verify_regressions.py",
        "limitations": "Counts, reachability and proposal consistency only; not a Dify DSL import, runtime binding, service implementation or business accuracy test."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    text = json.dumps(verify(), ensure_ascii=False, indent=2) + "\n"
    if args.write_report:
        (BASE / "static_validation.json").write_text(text, encoding="utf-8")
    print(text)
