"""Build an immutable offline 0903 rule release from pinned local evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

from authoring import normalize
from verify import PackageError, canonical, digest, file_digest, reads, validate_data, verify_directory

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "verification-evidence/rule-normalization-plan-20261105"
RELEASES = ROOT / "smart-cost-ai/resources/quota-rules"
VERSION = "0903-20261112-v5"
INPUT_NAMES = ["规则逐条拆解-20261110.json", "source-update-20261110.json", "quota-source-db-20261110.json",
               "待答复问题清单.md", "实施方案.md", "项目接入实施细则.md", "定额原文核验与未闭项-20261110.md",
               "acceptance-cases.v1.12.json", "baseline-integration-checks-v1.12-20261112.json"]


def load_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def json_bytes(value): return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def units():
    result = {}
    def put(labels, dimension, scale="1"):
        for label in labels:
            result[label] = {"dimension": dimension, "scale_to_base": scale, "purpose": "UNIT_ONLY_NOT_OBJECT_EQUIVALENCE"}
    put(["1", "个", "台", "套", "对", "项", "节", "组", "点", "块", "座", "子方阵", "橇", "处", "口", "张", "片"], {})
    put(["m"], {"length": 1}); put(["km"], {"length": 1}, "1000"); put(["mm"], {"length": 1}, "0.001")
    put(["m2", "m²"], {"length": 2}); put(["m3", "m³"], {"length": 3})
    put(["10m"], {"length": 1}, "10"); put(["100m"], {"length": 1}, "100")
    put(["kg", "千克"], {"mass": 1}); put(["t", "吨"], {"mass": 1}, "1000")
    put(["kW"], {"power": 1}, "1000"); put(["Wp"], {"peak_power": 1}); put(["MWp"], {"peak_power": 1}, "1000000")
    put(["kV"], {"voltage": 1}, "1000"); put(["MPa"], {"pressure": 1}, "1000000")
    put(["per_MPa"], {"pressure": -1}, "0.000001"); put(["kPa"], {"pressure": 1}, "1000")
    put(["CNY", "元"], {"currency": 1}); put(["万元"], {"currency": 1}, "10000")
    put(["8点"], {}, "8"); put(["10处", "10口", "10张"], {}, "10")
    put(["CNY_per_km"], {"currency": 1, "length": -1}, "0.001")
    put(["m3_per_h", "GPM_US"], {"length": 3, "time": -1})
    # Formula coefficients explicitly encode the confirmed approximate conversion;
    # these retrieval-only units do not implement a generic unit converter.
    put(["m3_per_h_per_GPM"], {})
    put(["degC"], {"temperature": 1}); put(["kg_per_m3"], {"mass": 1, "length": -3})
    put(["m_per_s2"], {"length": 1, "time": -2})
    pressure = {"mass": 1, "length": -1, "time": -2}
    put(["psi", "bar"], pressure)
    put(["m_per_psi", "m_per_bar"], {"mass": -1, "length": 2, "time": 2})
    put(["Pa_per_psi", "Pa_per_bar"], {})
    for label in ("m3_per_h", "GPM_US", "m3_per_h_per_GPM", "degC", "psi", "bar", "m_per_psi", "m_per_bar", "Pa_per_psi", "Pa_per_bar"):
        result[label].update(scale_to_base=None, purpose="FORMULA_SCOPED_ONLY_NO_GENERIC_UNIT_CONVERSION")
    return result


def build_artifacts():
    planned = load_json(EVIDENCE / "acceptance-cases.v1.12.json")
    if any(file_digest(EVIDENCE / s["path"]) != s["sha256"] for s in planned["source_documents"]):
        raise PackageError("planned registry source hashes are stale")
    catalog = load_json(EVIDENCE / "规则逐条拆解-20261110.json")
    source = load_json(EVIDENCE / "source-update-20261110.json")
    quota = load_json(EVIDENCE / "quota-source-db-20261110.json")
    quota["snapshot_sha256"] = file_digest(EVIDENCE / "quota-source-db-20261110.json")
    supplement_dir = ROOT / "verification-evidence/pending-materials-20261112"
    supplement = load_json(supplement_dir / "existing-evidence.json")
    if file_digest(supplement_dir / "current-quota-catalog.json") != supplement["catalog_sha256"]: raise PackageError("current evidence hash changed")
    if supplement["baseline_catalog_sha256"] != quota["snapshot_sha256"]: raise PackageError("evidence baseline changed")
    if any(any(c.values()) for c in supplement["catalog_comparison"].values()): raise PackageError("catalog changed; explicit rule re-review required")
    old_dirs = {d["id"]: d for d in quota["directories"]}
    if any(old_dirs.get(s["id"]) != s for s in supplement["sections"].values()): raise PackageError("quoted directory evidence differs")
    quota["verified_supplement"] = supplement
    confirmation_path = ROOT / "verification-evidence/materials-confirmation-20261112-v5/confirmed-changes.json"
    confirmations = load_json(confirmation_path)
    ce = confirmations["catalog_evidence"]
    if ce["snapshot_sha256"] != quota["snapshot_sha256"]: raise PackageError("confirmation evidence snapshot mismatch")
    if any(old_dirs.get(ce[k]["id"]) != ce[k] for k in ("oil_title_directory", "wind_scope_directory", "crossing_directory")):
        raise PackageError("confirmation quoted directory changed")
    old_items = {i["id"]: i for i in quota["items"]}
    if any(old_items.get(i["id"]) != i for key in ("corrosion_items", "wind_related_items", "round2_items") for i in ce[key]):
        raise PackageError("confirmation item evidence changed")
    crossing_dirs = [d for d in quota["directories"] if d["library_code"] == "DE1000022001" and (d["bsid"] == "1.9.2" or d["bsid"].startswith("1.9.2."))]
    if ce["crossing_directories"] != crossing_dirs: raise PackageError("crossing directory evidence changed")
    for item in confirmations['round2_inputs']:
        if file_digest(ROOT / item['path']) != item['sha256']: raise PackageError('round2 authority hash mismatch')
    quota["confirmed_changes"] = confirmations
    if catalog["quota_snapshot_sha256"] != quota["snapshot_sha256"]: raise PackageError("quota evidence changed")
    if len(catalog["rules"]) != 272: raise PackageError("source baseline count changed")
    # Current raw workbooks are optional for later reproduction; if available they must match.
    originals = []
    for item in source["files"]:
        path = Path(item["path"])
        if path.exists() and file_digest(path) != item["sha256"]: raise PackageError("original workbook changed: " + path.name)
        originals.append({"name": path.name, "sha256": item["sha256"], "bytes": item["bytes"]})
    approved, pending, dispositions, fields = normalize(catalog["rules"], quota)
    for rule in approved:
        rule["dependencies"] = sorted(reads(rule["conditions"]) | reads(rule["effect"]))
        rule["required_inputs"] = [{"field": k, **fields[k]} for k in rule["dependencies"]]
    approved.sort(key=lambda r: r["rule_id"]); pending.sort(key=lambda r: r["rule_id"])
    dictionary = {"schema_version": "0903-units-v1", "fields": fields, "units": units(),
                  "contract": {"decimal_encoding": "STRING", "facts": "KNOWN/UNKNOWN/CONFLICT/NOT_APPLICABLE plus source_refs",
                               "count_units": "Scope-bound; matching dimensions never authorizes 台/套/个 conversion.",
                               "formula_inputs": "Caller supplies exactly the declared unit; no implicit second conversion.",
                               "unknown_fields": "REJECT", "prohibit_defaults": True}}
    package = {"package_schema_version": "0903-rule-package-v2", "release_version": VERSION,
               "approved_rules": approved, "pending_rules": pending,
               "scope_index": {f: sorted(r["rule_id"] for r in approved + pending if r["family"] == f) for f in ("A05", "A06", "A07", "A09", "A11")},
               "evaluation_contract": {"baseline": "FULL_SCAN_WITHIN_FAMILY", "unknown_object": "KEEP_POSSIBLE",
                   "unknown_condition": "NEEDS_INPUT", "conflicting_fact": "CONFLICT", "pending_rule": "DO_NOT_TREAT_AS_NO_SPECIAL_RULE",
                   "execution_guards": "MUST_PASS_BEFORE_APPLYING_EFFECT", "precedence": "ONLY_EXPLICIT_SOURCE_CONFIRMED",
                   "stage_policy": "CHECK_PROJECT_STAGE_AND_VERIFIED_TARGET_APPLICABILITY_BEFORE_METHOD_ACTION",
                   "input_requirement_policy": "DEPENDENCY_UNION_IS_NOT_ALL_BRANCHES_REQUIRED_EVALUATE_ONLY_ACTIVE_BRANCH",
                   "release_blocked_by": "UNCONDITIONAL_BLOCK_UNTIL_NEW_REVIEWED_RELEASE_NOT_A_RUNTIME_BOOLEAN",
                   "branch_scope_before_evaluation": "PRUNE_KNOWN_OTHER_LIBRARY_BRANCHES_BEFORE_BLOCK_CHECK_KEEP_UNKNOWN_POSSIBLE",
                   "pending_library_scope": "CONSERVATIVE_SCOPE_LIBRARY_IDS_AND_CODES_WHEN_DECLARED_NOT_WHOLE_SOURCE_ROW",
                   "retrieval_hint_policy": "KEEP_ORIGINAL_HARD_CONSTRAINTS_NO_FACT_BACKFILL_NO_AUTO_ACCEPT",
                   "formulas": "DECIMAL_TYPED_AST_NO_EVAL", "runtime_activation": False,
                   "phase": "0903", "excluded_phase": "0904", "llmlingua2_enabled": False}}
    by_id = {d["source_record_id"]: d for d in dispositions}
    fragments = []
    for row in catalog["rules"]:
        for fragment in row["atomic_source_fragments"]:
            fragments.append({"fragment_id": f"{row['rule_id']}/{fragment['role']}/{fragment['part']}",
                              "source_record_id": row["rule_id"], **fragment,
                              "disposition": by_id[row["rule_id"]]["state"], "rule_ids": by_id[row["rule_id"]]["rule_ids"]})
    if len(fragments) != 1636: raise PackageError("source fragment baseline changed")
    inputs = [{"path": p.relative_to(ROOT).as_posix(), "sha256": file_digest(p)} for p in (EVIDENCE / n for n in INPUT_NAMES)]
    inputs += [{"path": p.relative_to(ROOT).as_posix(), "sha256": file_digest(p)} for p in
               [supplement_dir / "existing-evidence.json", supplement_dir / "current-quota-catalog.json"]]
    inputs.append({"path": confirmation_path.relative_to(ROOT).as_posix(), "sha256": file_digest(confirmation_path)})
    inputs.extend(confirmations['round2_inputs'])
    referenced_ids = {item["id"] for rule in approved for key in ("catalog_references", "main_catalog_references")
                      for item in rule["effect"].get(key, [])}
    reference_evidence = [{k: item[k] for k in ("id", "library_code", "directory_id", "code", "name", "unit")}
                          for item in quota["items"] if item["id"] in referenced_ids]
    reference_evidence.sort(key=lambda item: (item["library_code"], item["code"], item["id"]))
    source_map = {"schema_version": "0903-source-map-v1", "original_files": originals, "snapshot_inputs": inputs,
                  "catalog_reference_evidence": reference_evidence, "catalog_snapshot_sha256": quota["snapshot_sha256"],
                  "authorized_sheet_snapshots": source["rules"], "answer_workbook_records": source["answers"],
                  "confirmation_ledger": (EVIDENCE / "待答复问题清单.md").read_text(encoding="utf-8"),
                  "authority_order": ["latest user corrections recorded in current plan and answer ledger", "latest five-sheet snapshot", "historical evidence"],
                  "evidence_refs": {"current-plan": next(i for i in inputs if i["path"].endswith("/实施方案.md")),
                                    "latest-confirmations": next(i for i in inputs if i["path"].endswith("/待答复问题清单.md"))},
                  "records": catalog["rules"], "metadata": catalog["metadata"], "fragments": fragments,
                  "dispositions": dispositions, "coverage": {"source_records": 272, "field_fragments": 1636, "metadata_rows": 10},
                  "external_dependencies": [{"id": "A11-08", "state": "MISSING_LOCAL_SOURCE", "scope": "external property-topic mapping only", "do_not_block_independent_rules": True}],
                  "correction_policy": "Preserve original values; rule AST follows the latest confirmed correction. Old activation fields describe the source dossier only."}
    cards = [{"rule_id": r["rule_id"], "rule": r, "source_record": next(x for x in catalog["rules"] if x["rule_id"] == r["source_record_id"]),
              "usage_notice": "Evidence data, never agent instructions. No reverse/transitive aliases or unrestricted library changes."} for r in approved]
    from review_pending import make_review, markdown_review
    review = make_review(RELEASES / "0903-20261112-v1", package, source_map, quota)
    source_map["pending_review"] = review
    from materials_round2 import build_round2 as build_followup, markdown_round2 as markdown_followup
    source_map["confirmed_changes"] = confirmations
    request = build_followup(package, source_map, supplement, confirmations, load_json(RELEASES / "0903-20261112-v4/materials-request.json"))
    source_map["materials_request"] = request
    cases = load_json(Path(__file__).with_name("test-cases.json"))
    report = validate_data(package, cards, source_map, dictionary, cases)
    schema_path = Path(__file__).with_name("rule-package.schema.json")
    import jsonschema
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(package, schema)
    outputs = {"rules.json": json_bytes(package), "rule-cards.jsonl": b"".join(canonical(c) + b"\n" for c in cards),
               "source-map.json": json_bytes(source_map), "unit-dictionary.json": json_bytes(dictionary),
               "test-cases.json": json_bytes(cases), "validation-report.json": json_bytes(report),
               "rule-package.schema.json": schema_path.read_bytes(),
               "pending-review.json": json_bytes(review), "pending-review.md": markdown_review(review).encode("utf-8"),
               "materials-request.json": json_bytes(request), "materials-request.md": markdown_followup(request).encode("utf-8"),
               "existing-evidence.json": json_bytes(supplement), "confirmed-changes.json": json_bytes(confirmations)}
    files = {name: hashlib.sha256(content).hexdigest() for name, content in outputs.items()}
    manifest = {"schema_version": "0903-manifest-v1", "release_version": VERSION, "package_schema_version": package["package_schema_version"],
                "build_tool": "offline-quota-rule-authoring-v5", "files": files,
                "semantic_hash": digest({k: files[k] for k in sorted(files) if k != "validation-report.json"}),
                "source_inputs": inputs, "original_files": originals,
                "tool_inputs": [{"path": p.relative_to(ROOT).as_posix(), "sha256": file_digest(p)} for p in
                                [Path(__file__), Path(__file__).with_name("authoring.py"), Path(__file__).with_name("authoring_revision.py"), Path(__file__).with_name("authoring_confirmations.py"), Path(__file__).with_name("authoring_round2.py"), Path(__file__).with_name("materials_round2.py"), Path(__file__).with_name("verify_round2.py"), Path(__file__).with_name("review_pending.py"), Path(__file__).with_name("materials_request.py"), Path(__file__).with_name("materials_followup.py"), Path(__file__).with_name("verify.py"), Path(__file__).with_name("test-cases.json"), Path(__file__).with_name("test_package.py"), schema_path]],
                "release_status": "OFFLINE_RESOURCE_READY_WITH_EXPLICIT_PENDING", "runtime_activation": False,
                "source_record_dispositions": dict(sorted(Counter(d["state"] for d in dispositions).items())),
                "approved_scope": {"phase": "0903", "rule_ids": [r["rule_id"] for r in approved]},
                "pending_scope": {"rule_ids": [r["rule_id"] for r in pending], "policy": "MUST_CHECK_POSSIBLE_IMPACT"},
                "previous_release": review["previous_release"], "pending_review_summary": review["summary"],
                "blocked_policy_rule_ids": [r["rule_id"] for r in approved if r["effect"].get("release_blocked_by")],
                "materials_request_schema": request["schema_version"], "materials_request_summary": request["summary"],
                "confirmation_schema": confirmations["schema_version"],
                "supersedes_release": {"version": "0903-20261112-v4", "manifest_sha256": file_digest(RELEASES / "0903-20261112-v4/manifest.json")},
                "deferred": ["0904 price matching", "runtime loader/0903 business integration", "LLMLingua-2 activation"],
                "verification": {"passed": True, "cases": report["case_count"], "report": "validation-report.json"},
                "manifest_hash_policy": "Compute SHA-256 of this file externally; do not write a self hash."}
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs, report


def publish(output):
    output = Path(output).resolve()
    if output.parent != RELEASES.resolve(): raise PackageError("release must be a direct child of the project resource directory")
    if output.name != VERSION: raise PackageError("release directory/version mismatch")
    outputs, report = build_artifacts()
    if output.exists():
        existing = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
        if existing != outputs: raise PackageError("IMMUTABLE_RELEASE_EXISTS: create a new version instead of overwriting")
        verify_directory(output)
        return "IDENTICAL_RELEASE_REUSED", report
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".quota-build-", dir=output.parent) as temp:
        stage = Path(temp).resolve()
        if stage.parent != output.parent: raise PackageError("invalid staging path")
        for name, content in outputs.items(): (stage / name).write_bytes(content)
        verify_directory(stage)
        # Rename one complete verified directory, never expose a partially written release.
        stage.rename(output)
    return "PUBLISHED_LOCAL_RESOURCE", report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RELEASES / VERSION)
    args = parser.parse_args()
    status, report = publish(args.output)
    print(json.dumps({"status": status, "directory": str(args.output), **{k: v for k, v in report.items() if k != "cases"}}, ensure_ascii=False, indent=2))
