"""Render the v4 follow-up without reopening the answered v3 material requests."""
from copy import deepcopy
from html import escape

from materials_request import GROUPS, candidate_text


def build_followup(package, source_map, evidence, confirmations, previous):
    pending = {r["rule_id"]: r for r in package["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    reviews = {r["source_record_id"]: r for r in source_map["pending_review"]["records"]}
    before = {r["rule_id"] for r in previous["rule_index"]}
    closed = sorted(before - set(pending))
    if set(pending) - before or closed != sorted(confirmations["expected_newly_closed_rule_ids"]): raise ValueError("unexpected closure scope")
    groups = deepcopy(GROUPS)
    answers = {
        "D01": "用户确认仅A06第64—70、72—73行对应DE1000022001。正式刊名概算指标与源概算定额分别保留，不生成全局书名别名。本组已答，无需再确认。",
        "D09": "用户修订：第70行不再挂土方。主项编号空、m与10m²不一致及10m算式矛盾均保留历史；不把面积变成长度，不保留唯一计价行回补例外。保留管道安装行既有土方规则，按实际范围核实同沟防重，不推定已计。",
        "D12": "用户确认R006/R087/R091为R005/R086/R090对象的第二级依据，只限这三行。首级未覆盖必须针对同一工作范围核实；R087保留已含防腐不计，R091限第九章第二节并沿用单出图等条件。",
        "D03": "D03②已答：撤销R072/073风电分支，保留石油和光伏分支。D03①指南与风电库身份仍未确认；只保留R078—081的身份资料需求。"}
    for g in groups:
        gid = g["id"]
        g["pending_rule_ids"] = [rid for rid in g["rule_ids"] if rid in pending]
        g["answer"] = answers.get(gid, "本轮没有新的用户确认，沿用原待补范围及既有已答口径。")
        if gid in ("D01", "D09", "D12"):
            g.update(status="CLOSED", pending_rule_ids=[], request="无需补充或重复确认。", accepted="用户本轮答复已记录并形成新版本。", completion=answers[gid])
        elif gid == "D03":
            g.update(status="PARTIAL", pending_rule_ids=[f"A06-R{n:03d}" for n in range(78,82)],
                     request="仅D03①仍需：陆上风电2023指南与DE07000022安装单位估价表的明确对应范围，提供限定版次/篇章的书面确认，或指南封面/目录及安装表对应页。R072/073风电分支已撤销，不再索要4-3176。",
                     accepted="指南身份映射确认或相应资料页；不重答风机费用公式。",
                     completion="仅核R078—081的F-b4指南身份；R072/073风电分支撤销保持。")
        else: g["status"] = "OPEN"
        if gid == "D02": g["completion"] = "补齐光伏身份及G-b2候选绑定；R072/073石油分支已闭合、风电分支已撤销，仅光伏仍阻断。"
        if gid == "D04": g["completion"] = "需区分同壁厚下胶片尺寸；R069的D01库映射已答，本行只剩胶片条款。"
        if gid == "D09": g["known"] = "已核石油2022第六章6-2094～6-2102共9条埋地管线防腐，单位10m²；源主项编号空、主量m与10m土方算式矛盾保留为历史。用户据此取消本行土方关联。"
        if gid == "D12": g["known"] = "源B6/B87/B91原空白保留。用户已明确三行分别承接R005站外管线/R086防腐/R090穿跨越，R48/R49为同表显式先例；本次确认只适用于这三行。第九章第二节目录已核实。"
    index = []
    for rid, row in sorted(pending.items()):
        review = reviews[rid]
        index.append({"rule_id": rid, "groups": [g["id"] for g in groups if rid in g["pending_rule_ids"]],
                      "source_refs": row["source_refs"], "source_values": review["source_values"],
                      "candidate_checks": review["catalog_checks"], "generated_rule_ids": review["generated_rule_ids"],
                      "missing_evidence": review["missing_evidence"], "pending_scope": row["conservative_scope"]})
    return {"schema_version": "0903-materials-request-v2", "release_version": package["release_version"],
            "summary": {"baseline_unique_rules": len(before), "unique_rules": len(pending), "groups": len(groups),
                        "active_groups": sum(bool(g["pending_rule_ids"]) for g in groups),
                        "group_rule_links": sum(len(g["pending_rule_ids"]) for g in groups), "newly_closed": len(closed), "deferred_0904": 5},
            "baseline_rule_ids": sorted(before), "newly_closed_rule_ids": closed, "groups": groups, "rule_index": index,
            "existing_evidence": evidence, "confirmed_changes": confirmations,
            "shared_electricity_request": previous["shared_electricity_request"],
            "scope_note": "本轮只采纳四项直接用户答复；D02、D03①、D04—08、D10—11仍按所缺依据处理，0904后续。"}


def markdown_followup(data):
    def cell(value): return str(value).replace("|", "\\|").replace("\n", "<br>")
    s = data["summary"]
    lines = ["# 0903待补资料跟进清单", "", f"资源版本：`{data['release_version']}`。由用户本轮D01、D09、D12、D03②答复更新，旧v3保留。",
             "", f"**技术待核{s['baseline_unique_rules']}→{s['unique_rules']}条，本轮闭合{s['newly_closed']}条。** 原12组保留跟踪，其中{s['active_groups']}组仍需资料，共{s['group_rule_links']}处待补关联。已答D01/D09/D12及D03②不重复提问。",
             "", "新增闭合：" + "、".join(data["newly_closed_rule_ids"]), "",
             "R072/073按库拆分：石油分支绑定真实子目，光伏分支保持发行阻断，风电分支明确撤销。源行因光伏未闭合仍计入待核，不能把一个分支完成算作整行闭合。",
             "", "## 12组处理结果", "", "| 组 | 状态 | 当前需补规则行 | 本轮处理 |", "|---|---|---|---|"]
    labels = {"CLOSED": "已答，无需补充", "PARTIAL": "部分已答", "OPEN": "仍需资料"}
    for g in data["groups"]:
        lines.append("| " + " | ".join(cell(x) for x in [g["id"]+" "+g["title"], labels[g["status"]], "、".join(g["pending_rule_ids"]) or "—", g["answer"]]) + " |")
    lines += ["", "## 仍需提供的资料", "", "电力D05—D08共用确认仍只需一次：" + data["shared_electricity_request"]]
    for g in data["groups"]:
        if not g["pending_rule_ids"]: continue
        lines += ["", f"## {g['id']}　{g['title']}", "", "**对应行：**"+"、".join(g["pending_rule_ids"]),
                  "", "**已有候选：**"+g["known"], "", "**需要补充：**"+g["request"],
                  "", "**最小资料：**"+g["accepted"], "", "**已答，不再询问：**"+g["already_answered"],
                  "", "**收到后的处理：**"+g["completion"]]
    lines += ["", f"## {s['unique_rules']}条逐行索引", "", "| 规则行 | 待补组 | 尚缺依据 | 已有候选 |", "|---|---|---|---|"]
    for r in data["rule_index"]:
        lines.append("| " + " | ".join(cell(x) for x in [r["rule_id"], "、".join(r["groups"]), "；".join(r["missing_evidence"]), candidate_text(r)]) + " |")
    lines += ["", "原源表和旧答复保留不改；最新用户修订优先于历史算例。D10/D11只收已有更正资料，无资料继续待补，不重开已忽略问卷。",
              "", "[版本、修改文件、启动方式、测试地址、用例与结果](../../../../verification-evidence/materials-confirmation-20261112-v4/交接与验收.md)。本轮仅离线资源，0904仍后续，未接入业务。", ""]
    return "\n".join(lines)


def html_followup(data):
    s = data["summary"]
    panels = []
    labels = {"CLOSED": "已答，无需补充", "PARTIAL": "部分已答", "OPEN": "仍需资料"}
    for g in data["groups"]:
        panels.append(f'<section id="{g["id"]}" class="group"><h2>{escape(g["id"]+"　"+g["title"])}</h2><p>状态：{escape(labels[g["status"]])}</p><p>原对应行：{escape("、".join(g["rule_ids"]))}</p><p>当前待补：{escape("、".join(g["pending_rule_ids"]) or "无")}</p><p>{escape(g["answer"])}</p><p>已有候选：{escape(g["known"])}</p><p>需要补充：{escape(g["request"])}</p><p>已答：{escape(g["already_answered"])}</p></section>')
    rows = ''.join(f'<tr><td>{escape(r["rule_id"])}</td><td>{escape("、".join(r["groups"]))}</td><td>{escape("；".join(r["missing_evidence"]))}</td></tr>' for r in data["rule_index"])
    nav = ' '.join(f'<a href="#{g["id"]}">{g["id"]}</a>' for g in data["groups"])
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0903资料答复跟进</title><style>body{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;background:#f4f7fa;color:#203040;margin:0}main{max-width:1100px;margin:auto;padding:24px}header,section{background:white;border:1px solid #ccd8e3;border-radius:10px;padding:20px;margin:16px 0}a{color:#185b9b;margin-right:12px}input{font:inherit;padding:10px;width:min(90%,600px)}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ccd8e3;padding:8px;text-align:left}p,td{overflow-wrap:anywhere}</style><main><header><h1>0903资料答复跟进</h1><p>'+escape(data['release_version'])+f' · 41→{s["unique_rules"]}条技术待核 · 闭合{s["newly_closed"]}条 · {s["active_groups"]}组仍需资料</p><p>本页只读，不接业务服务；已答组保留结果，无需重新回答。0904后续。</p><nav>'+nav+'</nav><p><label for="search">查找规则或资料组</label><br><input id="search" placeholder="例如 A06-R069、D01"><span id="count" aria-live="polite">12 / 12 组</span></p></header>'+''.join(panels)+'<section><h2>32条待补索引</h2><table><thead><tr><th>规则行</th><th>资料组</th><th>尚缺依据</th></tr></thead><tbody>'+rows+'</tbody></table></section></main><script>const search=document.querySelector("#search");function filterGroups(){const q=search.value.trim().toLowerCase();let n=0;document.querySelectorAll(".group").forEach(s=>{const yes=s.textContent.toLowerCase().includes(q);s.hidden=!yes;if(yes)n++});document.querySelector("#count").textContent=`${n} / 12 组`;}search.addEventListener("input",filterGroups);document.querySelectorAll("nav a").forEach(a=>a.addEventListener("click",()=>{search.value="";filterGroups();}));</script></html>'
