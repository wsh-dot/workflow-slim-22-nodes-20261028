"""Offline mutation/regression tests, independent of the business test suite."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from build import build_artifacts
from verify import PackageError, condition_shape, dimension, evaluate_condition, evaluate_formula, policy_status, pv_plan, strict_json, validate_data, verify_directory
from authoring_round2 import PV_ROWS, WIND_ROWS, FILM_ROWS
ROUND2_ROWS = PV_ROWS | WIND_ROWS | FILM_ROWS


class OfflinePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs, cls.report = build_artifacts()
        cls.rules = json.loads(cls.outputs["rules.json"])
        cls.cards = [json.loads(line) for line in cls.outputs["rule-cards.jsonl"].splitlines()]
        cls.source = json.loads(cls.outputs["source-map.json"])
        cls.dictionary = json.loads(cls.outputs["unit-dictionary.json"])
        cls.cases = json.loads(cls.outputs["test-cases.json"])

    def check_data(self, **overrides):
        args = dict(rules=self.rules, cards=self.cards, source_map=self.source, dictionary=self.dictionary, cases=self.cases)
        args.update(overrides)
        return validate_data(**args)

    def test_reproducible_build(self):
        other, report = build_artifacts()
        self.assertEqual(self.outputs, other)
        self.assertEqual(self.report, report)

    def test_every_source_cell_and_fragment_handled(self):
        self.assertEqual(self.report["source_records"], 272)
        self.assertEqual(self.report["field_fragments"], 1636)
        self.assertEqual(self.report["raw_cells"], 1307)
        self.assertTrue(self.report["passed"])

    def test_missing_fragment_rejected(self):
        source = deepcopy(self.source); source["fragments"].pop()
        with self.assertRaisesRegex(PackageError, "fragment loss"):
            self.check_data(source_map=source)

    def test_raw_source_not_rewritten(self):
        source = deepcopy(self.source)
        source["records"][0]["source_cells"]["A3"]["value"] = "changed"
        with self.assertRaisesRegex(PackageError, "source cell altered"):
            self.check_data(source_map=source)

    def test_cards_cannot_drop_exceptions(self):
        cards = deepcopy(self.cards)
        cards[0]["rule"]["conditions"] = {"op": "EQ", "field": "object.kind", "value": "anything"}
        with self.assertRaisesRegex(PackageError, "card differs"):
            self.check_data(cards=cards)

    def test_dependency_in_not_and_group_keys_retained(self):
        rule = next(r for r in self.rules["approved_rules"] if r["rule_id"] == "A05-R010")
        self.assertIn("pipeline.outer_diameter_mm", rule["dependencies"])
        rule = next(r for r in self.rules["approved_rules"] if r["rule_id"] == "A06-R037")
        self.assertIn("group.single_project_id", rule["dependencies"])
        changed = deepcopy(self.rules); changed["approved_rules"][0]["dependencies"] = []
        with self.assertRaisesRegex(PackageError, "dependency loss"):
            self.check_data(rules=changed)

    def test_pending_rules_cannot_disappear_from_index(self):
        rules = deepcopy(self.rules); rules["scope_index"]["A05"].remove("A05-R021")
        with self.assertRaisesRegex(PackageError, "scope index omission"):
            self.check_data(rules=rules)

    def test_duplicate_ids_rejected(self):
        rules = deepcopy(self.rules); rules["approved_rules"].append(deepcopy(rules["approved_rules"][0]))
        with self.assertRaisesRegex(PackageError, "duplicate rule"):
            self.check_data(rules=rules)

    def test_fake_quota_id_rejected(self):
        rules, cards = deepcopy(self.rules), deepcopy(self.cards)
        changed = rules["approved_rules"][0]
        changed["effect"]["catalog_references"][0]["id"] = "invented-id"
        for card in cards:
            if card["rule_id"] == changed["rule_id"]: card["rule"] = deepcopy(changed)
        with self.assertRaisesRegex(PackageError, "catalog identity/evidence mismatch"):
            self.check_data(rules=rules, cards=cards)

    def test_no_arbitrary_ast_or_zero_divisor(self):
        for expression in [{"op":"EVAL", "value":"__import__('os')"},
                           {"op":"DIV", "args":[{"op":"CONST","value":"1","unit":"1"},{"op":"CONST","value":"0","unit":"1"}]}]:
            with self.assertRaises(PackageError): dimension(expression, self.dictionary["fields"], self.dictionary["units"])
        rules = deepcopy(self.rules)
        rules["approved_rules"][0]["effect"]["formula"] = {"op":"RUN_SCRIPT", "script":"not executable"}
        with self.assertRaisesRegex(PackageError, "unsupported embedded op"):
            self.check_data(rules=rules)

    def test_dimensional_error_rejected(self):
        expression = {"op":"ADD", "args":[{"op":"CONST","value":"1","unit":"m"},{"op":"CONST","value":"2","unit":"t"}]}
        with self.assertRaisesRegex(PackageError, "incompatible addition"):
            dimension(expression, self.dictionary["fields"], self.dictionary["units"])

    def test_three_value_truth_tables(self):
        leaf = lambda k: {"op":"EQ","field":k,"value":True}
        facts = {"t":True,"f":False}
        for op, keys, expected in [("AND",["f","u"],"FALSE"),("AND",["t","u"],"UNKNOWN"),
                                   ("OR",["t","u"],"TRUE"),("OR",["f","u"],"UNKNOWN")]:
            self.assertEqual(evaluate_condition({"op":op,"args":[leaf(k) for k in keys]},facts),expected)
        self.assertEqual(evaluate_condition({"op":"NOT","arg":leaf("u")},facts),"UNKNOWN")

    def test_decimal_not_float_and_missing_not_zero(self):
        with self.assertRaises(PackageError): evaluate_formula({"op":"CONST","value":0.1,"unit":"1"},{})
        with self.assertRaises(PackageError): evaluate_formula({"op":"CONST","value":"NaN","unit":"1"},{})
        with self.assertRaisesRegex(PackageError,"NEEDS_INPUT"):
            evaluate_formula({"op":"READ","field":"missing","unit":"m"},{})
        with self.assertRaisesRegex(PackageError,"duplicate JSON key"): strict_json('{"a":1,"a":2}')

    def test_scoped_valve_actuator_branches_distinct(self):
        rules = {r["rule_id"]:r for r in self.rules["approved_rules"]}
        def find_values(node, name):
            found=[]
            if isinstance(node,dict):
                if node.get("field")==name: found.append(node.get("value"))
                for value in node.values(): found.extend(find_values(value,name))
            elif isinstance(node,list):
                for value in node: found.extend(find_values(value,name))
            return found
        self.assertEqual(find_values(rules["A06-R019"]["conditions"],"valve.actuator_type"),["gas_hydraulic"])
        self.assertEqual(find_values(rules["A06-R020"]["conditions"],"valve.actuator_type"),["electro_hydraulic"])

    def test_directory_hash_tamper_rejected(self):
        # Temporary paths are owned by this test; no existing project files are removed.
        with tempfile.TemporaryDirectory(prefix="smartcost-rule-test-") as temp:
            root=Path(temp)
            for name,content in self.outputs.items(): (root/name).write_bytes(content)
            verify_directory(root)
            with (root/"rules.json").open("ab") as out: out.write(b" ")
            with self.assertRaisesRegex(PackageError,"hash mismatch"):
                verify_directory(root)

    def test_v1_rules_and_deferred_0904_preserved(self):
        previous = Path(__file__).resolve().parents[2] / "resources/quota-rules/0903-20261112-v1/rules.json"
        old = json.loads(previous.read_text(encoding="utf-8"))
        current = {r["rule_id"]: r for r in self.rules["approved_rules"]}
        for rule in old["approved_rules"]:
            if rule["rule_id"] in ("A09-R005", "A09-R090"): continue  # Explicit D12 primary/fallback change.
            self.assertEqual(current[rule["rule_id"]], rule, rule["rule_id"])
        deferred = lambda data: [r for r in data["pending_rules"] if r["pending_kind"] == "PHASE_DEFERRED"]
        self.assertEqual(deferred(old), deferred(self.rules))

    def test_review_exactly_covers_original_95(self):
        previous = Path(__file__).resolve().parents[2] / "resources/quota-rules/0903-20261112-v1/rules.json"
        old = json.loads(previous.read_text(encoding="utf-8"))
        expected = {r["rule_id"] for r in old["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
        actual = {r["source_record_id"] for r in self.source["pending_review"]["records"]}
        self.assertEqual(actual, expected)
        self.assertEqual(self.source["pending_review"]["summary"]["remaining_technical"], 18)
        self.assertEqual(self.source["pending_review"]["summary"]["states"]["CLOSED_FOR_DECLARED_USAGE"], 77)
        changed = deepcopy(self.source); changed["pending_review"]["records"].pop()
        with self.assertRaisesRegex(PackageError, "review coverage"):
            self.check_data(source_map=changed)

    def test_partial_policies_are_blocked_for_any_runtime_facts(self):
        partial = [r for r in self.rules["approved_rules"] if r["effect"].get("release_blocked_by")]
        self.assertEqual(len(partial), 18)
        for rule in partial:
            facts = {k: True for k in rule["dependencies"]}
            self.assertEqual(policy_status(rule, facts), "BLOCKED_EVIDENCE", rule["rule_id"])

    def test_removing_film_project_evidence_guard_is_rejected(self):
        rules, cards = self.mutate_guard('A06-R010-POLICY', 'inspection.radiographic.plan_evidence_verified')
        with self.assertRaisesRegex(PackageError, "film evidence guard missing"):
            self.check_data(rules=rules, cards=cards)

    def test_retrieval_hints_cannot_promote_to_material_equivalence(self):
        rules = deepcopy(self.rules)
        rule = next(r for r in rules["approved_rules"] if r["rule_id"] == "A11-R066")
        rule["effect"]["creates_design_fact"] = True
        with self.assertRaisesRegex(PackageError, "retrieval hint exceeded"):
            self.check_data(rules=rules)

    def test_pv_splits_each_design_subarray(self):
        rule = next(r for r in self.rules["approved_rules"] if r["rule_id"] == "A06-R074-POLICY")
        spec = rule["effect"]["capacity_split"]
        a = pv_plan(spec, {"pv.subarray_capacity_mwp": "1"})
        b = pv_plan(spec, {"pv.subarray_capacity_mwp": "1"})
        self.assertEqual(a, {"G-b37": 1})
        self.assertEqual(b, {"G-b37": 1})
        self.assertNotEqual(a, pv_plan(spec, {"pv.subarray_capacity_mwp": "2"}))
        changed = deepcopy(spec); changed["tiers"][0]["target_source_code"] = "invented"
        with self.assertRaisesRegex(PackageError, "invalid PV split"):
            pv_plan(changed, {"pv.subarray_capacity_mwp": "9"})

    def test_bound_inspection_guards_do_not_default_true(self):
        rule = next(r for r in self.rules["approved_rules"] if r["rule_id"] == "A06-R009")
        facts = {"binding.library_id": "60812664-be98-3733-b099-3a8e35e6128a",
                 "selection.main_quota_id": "c3bf5c02-2ca8-3abd-a68f-efc1114fdcd6", "pipeline.lined": False,
                 "inspection.ultrasonic.required_by_specification": True, "inspection.ultrasonic.quantity_basis_verified": True}
        self.assertEqual(policy_status(rule, facts), "NEEDS_INPUT")
        facts.update({"evidence.target_identity_unit_and_chapter_verified": True, "evidence.same_work_not_already_charged": True})
        self.assertEqual(policy_status(rule, facts), "CONDITIONS_AND_GUARDS_PASS_INPUTS_STILL_REQUIRED")

    def test_v1_release_still_verifies(self):
        previous = Path(__file__).resolve().parents[2] / "resources/quota-rules/0903-20261112-v1"
        report = verify_directory(previous)
        self.assertEqual(report["approved_rules"], 149)
        self.assertEqual(report["case_count"], 46)
        second = previous.with_name("0903-20261112-v2")
        report = verify_directory(second)
        self.assertEqual(report["approved_rules"], 243)
        self.assertEqual(report["case_count"], 115)
        third = previous.with_name("0903-20261112-v3")
        report = verify_directory(third)
        self.assertEqual(report["approved_rules"], 244)
        self.assertEqual(report["case_count"], 120)
        fourth = previous.with_name("0903-20261112-v4")
        report = verify_directory(fourth)
        self.assertEqual(report["case_count"], 148)

    def test_materials_followup_covers_18_without_reopening_answers(self):
        request = self.source["materials_request"]
        self.assertEqual(request["summary"]["baseline_unique_rules"], 32)
        self.assertEqual(request["summary"]["unique_rules"], 18)
        self.assertEqual(request["summary"]["groups"], 12)
        self.assertEqual(request["summary"]["active_groups"], 6)
        self.assertEqual(request["summary"]["group_rule_links"], 21)
        self.assertNotIn('A06-R069', {r['rule_id'] for r in request['rule_index']})
        self.assertEqual(request["summary"]["newly_closed"], 14)
        self.assertEqual(request["existing_evidence"]["newly_closed_rule_ids"], [])

    def test_materials_group_loss_is_rejected(self):
        source = deepcopy(self.source)
        source["materials_request"]["groups"][4]["pending_rule_ids"].remove("A05-R021")
        with self.assertRaisesRegex(PackageError, "coverage"):
            self.check_data(source_map=source)

    def test_v2_core_rules_preserved_while_evidence_is_enriched(self):
        path = Path(__file__).resolve().parents[2] / "resources/quota-rules/0903-20261112-v2/rules.json"
        previous = json.loads(path.read_text(encoding="utf-8"))
        current = {r["rule_id"]: r for r in self.rules["approved_rules"]}
        for old in previous["approved_rules"]:
            if old["source_record_id"] in {f"A06-R{n:03d}" for n in (64,65,66,67,68,69,70,72,73)} | {"A09-R005","A09-R090"} | ROUND2_ROWS: continue
            new = current[old["rule_id"]]
            self.assertEqual(new["conditions"], old["conditions"])
            for key in ("formula", "quantity", "amount_formula", "capacity_split", "release_blocked_by", "catalog_references", "main_catalog_references", "candidate_policy"):
                self.assertEqual(new["effect"].get(key), old["effect"].get(key), old["rule_id"] + ":" + key)

    def test_v3_changes_are_exactly_the_authorized_source_rows(self):
        path=Path(__file__).resolve().parents[2]/"resources/quota-rules/0903-20261112-v3/rules.json"
        old=json.loads(path.read_text(encoding="utf-8"))
        current={r["rule_id"]:r for r in self.rules["approved_rules"]}
        expected={f"A06-R{n:03d}" for n in (64,65,66,67,68,69,70,72,73)} | {"A09-R005","A09-R090"} | ROUND2_ROWS
        changed={r["source_record_id"] for r in old["approved_rules"] if current[r["rule_id"]]!=r}
        self.assertEqual(changed,expected)
        for n in (65,67):
            rid=f"A06-R{n:03d}-POLICY"
            prior=next(r for r in old["approved_rules"] if r["rule_id"]==rid)
            self.assertEqual(current[rid]["effect"]["formula"],prior["effect"]["formula"])
            self.assertEqual(current[rid]["effect"]["group"],prior["effect"]["group"])

    def test_user_book_confirmation_is_not_a_global_alias(self):
        from authoring import library_for
        row=deepcopy(next(r for r in self.source["records"] if r["rule_id"]=="A06-R064"))
        row.update(rule_id="A06-R063",row=63)
        with self.assertRaisesRegex(ValueError,"BOOK_IDENTITY"): library_for(row)

    def test_row70_withdrawal_has_no_quantity_or_area_to_length_rule(self):
        rule=next(r for r in self.rules["approved_rules"] if r["rule_id"]=="A06-R070-POLICY")
        self.assertEqual(rule["effect"]["type"],"exclude_association")
        for key in ("formula","quantity","amount_formula","release_blocked_by"): self.assertNotIn(key,rule["effect"])
        self.assertFalse(any(k.startswith(("pipe.","trench.")) for k in rule["dependencies"]))

    def test_pv_branch_closed_without_reopening_wind(self):
        for n in (72,73):
            rid=f"A06-R{n:03d}"
            self.assertNotIn(rid,{r['rule_id'] for r in self.rules['pending_rules']})
            byid={r["rule_id"]:r for r in self.rules["approved_rules"]}
            self.assertNotIn("release_blocked_by",byid[rid+"-OIL2022"]["effect"])
            self.assertEqual(policy_status(byid[rid+"-POLICY"],{}),"NEEDS_INPUT")
            self.assertEqual(byid[rid+"-WIND_WITHDRAWN"]["effect"]["type"],"exclude_association")

    def test_scope_expansion_in_confirmation_is_rejected(self):
        source=deepcopy(self.source)
        source["confirmed_changes"]["decisions"][0]["rule_ids"].append("A06-R063")
        with self.assertRaisesRegex(PackageError,"confirmation scope expanded"):
            self.check_data(source_map=source)

    def mutate_guard(self,rid,field):
        rules,cards=deepcopy(self.rules),deepcopy(self.cards)
        rule=next(r for r in rules["approved_rules"] if r["rule_id"]==rid)
        rule["effect"]["execution_guards"]=[g for g in rule["effect"]["execution_guards"] if g.get("field")!=field]
        rule["dependencies"].remove(field)
        rule["required_inputs"]=[v for v in rule["required_inputs"] if v["field"]!=field]
        for card in cards:
            if card["rule_id"]==rid: card["rule"]=deepcopy(rule)
        return rules,cards

    def test_crossing_chapter_guard_cannot_be_omitted(self):
        rules,cards=self.mutate_guard("A09-R091","selection.target_directory_id")
        with self.assertRaisesRegex(PackageError,"crossing chapter guard missing"):
            self.check_data(rules=rules,cards=cards)

    def test_fallback_primary_unknown_never_selects_either_path(self):
        rules={r["rule_id"]:r for r in self.rules["approved_rules"]}
        facts={"context.route_subject":"油气集输-站外系统 -站外管线","context.location":"offsite",
               "coverage.standard_scope_matches_current_work":True,
               "binding.library_id":"60812664-be98-3733-b099-3a8e35e6128a",
               "evidence.method_target_in_allowed_scope_verified":True}
        for rid in ("A09-R005","A09-R006"):
            self.assertEqual(policy_status(rules[rid],facts),"NEEDS_INPUT")
        for available,expected in ((True,("TRUE","FALSE")),(False,("FALSE","TRUE"))):
            facts["coverage.standard_module_available_for_work"]=available
            actual=tuple(evaluate_condition(rules[rid]["conditions"],facts) for rid in ("A09-R005","A09-R006"))
            self.assertEqual(actual,expected)

    def test_answered_requests_are_closed_and_ignored_questions_stay_ignored(self):
        groups={g["id"]:g for g in self.source["materials_request"]["groups"]}
        for gid in ("D01","D02","D03","D04","D09","D12"):
            self.assertEqual(groups[gid]["status"],"CLOSED")
            self.assertEqual(groups[gid]["pending_rule_ids"],[])
        self.assertEqual(groups["D03"]["pending_rule_ids"],[])
        self.assertIn("不重开",groups["D10"]["request"])
        self.assertIn("不要求本轮重新回答",groups["D11"]["request"])

    def test_superseded_examples_preserve_historical_expected_values(self):
        retired={r["case"]["id"]:r for r in self.cases["superseded_cases"]}
        self.assertEqual(len(retired),8)
        self.assertEqual(retired["REV2-ROW70-ONE-METRE"]["case"]["expected_decimal"],"1.26")
        self.assertEqual(retired["REV2-EMPTY-SOURCE-SCOPE"]["authority"],"confirmed-changes:D12")

    def test_v4_only_fourteen_source_rows_changed(self):
        path=Path(__file__).resolve().parents[2]/'resources/quota-rules/0903-20261112-v4/rules.json'
        old=json.loads(path.read_text(encoding='utf-8'))
        current={r['rule_id']:r for r in self.rules['approved_rules']}
        self.assertEqual(set(current), {r['rule_id'] for r in old['approved_rules']})
        changed={r['source_record_id'] for r in old['approved_rules'] if r != current[r['rule_id']]}
        self.assertEqual(changed, ROUND2_ROWS)
        for r in old['approved_rules']:
            for key in ('formula','amount_formula','quantity','capacity_split','group'):
                self.assertEqual(current[r['rule_id']]['effect'].get(key),r['effect'].get(key),r['rule_id']+key)

    def test_film_same_scope_guard_cannot_be_removed(self):
        rules,cards=self.mutate_guard('A06-R069-POLICY','inspection.radiographic.target_and_quantity_same_scope_verified')
        with self.assertRaisesRegex(PackageError,'film evidence guard missing'):
            self.check_data(rules=rules,cards=cards)

    def test_film_auto_selection_cannot_be_enabled(self):
        rules,cards=deepcopy(self.rules),deepcopy(self.cards)
        rule=next(r for r in rules['approved_rules'] if r['rule_id']=='A06-R010-POLICY')
        rule['effect']['inspection_policy']['automatic_film_selection']=True
        for card in cards:
            if card['rule_id']==rule['rule_id']:card['rule']=deepcopy(rule)
        with self.assertRaisesRegex(PackageError,'film policy missing'):
            self.check_data(rules=rules,cards=cards)

    def test_retain_budget_targets_and_no_crossover(self):
        rules={r['rule_id']:r for r in self.rules['approved_rules']}
        for rid in ['A05-R021','A06-R087']+[f'A06-R{n:03d}' for n in range(96,100)]:
            r=rules[rid+'-POLICY']
            self.assertEqual(r['effect']['release_blocked_by'],[rid])
            self.assertEqual(policy_status(r,{}),'BLOCKED_EVIDENCE')


if __name__ == "__main__": unittest.main(verbosity=2)
