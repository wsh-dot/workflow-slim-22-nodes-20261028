"""One grouped evidence request, rendered as Markdown and a read-only preview."""
from collections import Counter
from html import escape
import json


def ids(family, *rows): return [f"{family}-R{row:03d}" for row in rows]


GROUPS = [
    {"id": "D01", "title": "石油2022源书名与现库的对应", "rule_ids": ids("A06", 64,65,66,67,68,69,70,72,73),
     "known": "现库DE1000022001为石油建设安装工程概算指标2022，库总说明也使用该正式标题；7-3193～3199、7-3216～3221、7-3237～3245、7-4006～4013、4-3176及关联项已核到。源行写的是“概算定额(2022版)”。",
     "request": "请确认：这9行的“概算定额(2022版)”是否就是现库DE1000022001的“概算指标2022”？确认只作用于这9行。若不是，请给真正使用的书名、版次、库代码或对应资料页。",
     "accepted": "一条明确的本项目规则映射确认即可；或给原资料封面/目录与导入来源对照。无需再次说明冲洗、执行机构或0.4/0.3公式。",
     "already_answered": "阀门关联全带、管沟扣除已计量、72/73独立计算及三种型号门槛。",
     "completion": "仅本名称对应可解除；R069还需D04，R070还需D09，R072/073还需D02/D03。"},
    {"id": "D02", "title": "光伏2022指南与现库的对应", "rule_ids": ids("A06",72,73,74,75,76,77)+ids("A07",12),
     "known": "候选库DE06000003“石油工程光伏定额（2022试行）”；4-3176、4-3141/3143、G-b1、G-b37～40均存在；“固定支架 安装”已查得G-b2、单位t。总说明为光伏项目补充单位估价表，但未写明与源指南同一版本。",
     "request": "请确认该库是否承载规则表所用《光伏发电项目投资编制与工程量清单计价指南（试行）（2022）》的安装单位估价表，并覆盖上述编号和G-b2固定支架；如是，给导入来源/所对应篇章或确认范围；如不是，指出正确库或提供相应表页。",
     "accepted": "指南封面/目录＋安装估价表对应页，或明确库代码、版次、篇章范围的现有导入对照/书面确认。",
     "already_answered": "按设计划分子方阵、9MWp按4+4+1、支架总重优先/单重乘数量、缺设计重量待补。",
     "completion": "可闭合本库身份和G-b2候选绑定；同一R072/073的石油/风电分支不能据此自动生效。"},
    {"id": "D03", "title": "风电2023指南对应与电缆条目适用范围", "rule_ids": ids("A06",72,73,78,79,80,81),
     "known": "候选库DE07000022“中石油陆上风电场安装工程单位估价表（2023试行）”；F-b4（轮毂高度120～130m、台）和4-3141/3143有记录，主项4-3176未检得。库总说明为补充单位估价表，不能单凭简称确认整部指南。",
     "request": "①请确认源《陆上风电场项目投资编制与工程量清单计价指南（试行）（2023）》与该库安装估价表的对应范围。②R072/073的4-3176是否确实应适用此风电版本：若适用，补该库真实主项及关联页；若源表把风电列入有误，明确仅撤销该风电分支，不能影响石油/光伏。",
     "accepted": "一次提供封面/目录、对应安装表页及4-3176缺项处理说明；无需重发所有风机费用公式。",
     "already_answered": "50963/298/5969/18916暂作企业参数、按每台风机计；50km只是估算，实际距离属项目输入。",
     "completion": "F-b4费用策略与电缆分支分别验收；不存在的主项不因库名确认而自动补造。"},
    {"id": "D04", "title": "射线探伤胶片规格选择条款", "rule_ids": ids("A06",10,14,69),
     "known": "石油2022库3-2202为80×150mm胶片/单壁厚8mm以内，3-2204为80×300mm/同一壁厚档；相关目录只写拍片等工作，没有选用两种长度的规则。",
     "request": "请提供石油2022射线探伤章说明中胶片尺寸如何选用的条款或表格及页码，含适用条件、例外和所引用表；如该尺寸条款同时约束张数，附该部分即可。若由经批准的企业规则补充，请给原规则及适用范围。检测方法和比例口径不重新询问。",
     "accepted": "相关说明页及表格即可，不需要整套原书。现库原文不足以判定，不能只回复“按壁厚”。",
     "already_answered": "按说明书选择检测/热处理；13—16行删编号排除但保留衬里约束；检测比例按具体设计/说明，不重复问。",
     "completion": "需能区分相同壁厚下的胶片规格；R069同时受D01库身份约束。"},
    {"id": "D05", "title": "35kV电缆实际目标子目", "rule_ids": ids("A05",21),
     "known": "旧YD8-46/20kV名称已确认错误。现库第7章四.2明确：厂站内35kV及以上高压电缆敷设、终端、调试转电力预算2018第五册相应子目。当前9个库未有电力预算2018库。源35kV样例未提供敷设位置。",
     "request": "请补本ZC-YJHLY23-26/35-3×95mm²样例应使用的真实编号、名称、单位及所在册/章/页；厂站内场景优先给预算2018第五册相关页。若采用其他依据，给实际适用条款及对应库。",
     "accepted": "特定子目页＋适用说明＋库/版次对应；敷设位置由具体项目提供，当前不要求给所有项目统一位置。",
     "already_answered": "四库示例的独立映射职责保留，错误对应失效；不重新问是否保留第21行。",
     "completion": "明确当前任务允许库和真实目标，站外不得沿用仅限厂站内的条款；不会自动切库。"},
    {"id": "D06", "title": "变压器与绝缘油过滤的编号及包含工作", "rule_ids": ids("A06",87),
     "known": "源YD2-20→YD2-91均未检得。现库候选GD2-13为110kV三相三绕组120000kVA以内、台；候选是概算编码，尚未证明与源安装工作及独立油过滤相同。",
     "request": "按前述电力共用确认给出本行实际采用的版本/册；提供源YD2-20、YD2-91（或经核准替代子目）的名称、单位、工作内容及是否包含油过滤的说明。",
     "accepted": "两项子目及章说明相关页/正式导入数据即可；若改用GD2-13，请明确对应范围及过滤工作防重依据，不只替换编号。",
     "already_answered": "工程量依设计实际油量取t；缺油量是项目输入，不重新要求企业默认油重。",
     "completion": "安装和过滤的身份、单位、覆盖均核实；不凭名称相似或同容量绑定。"},
    {"id": "D07", "title": "调相机安装、调试和试验的对应", "rule_ids": ids("A06",88,89,90,92,93,94,95),
     "known": "源主项YJ16-2单位组；现库候选GJ14-2同为300Mvar空冷调相机、单位台。源关联YS5-196、YS6-53/57、YS7-164/166/167/168未检得。概算调试总说明把未含特殊调试等指向预算2018第六册；不能据此认定每条都是特殊试验。",
     "request": "提供主项及上述7项的实际来源册/页、单位和工作内容；补组→台是否以及如何对应的依据。可一次提供预算第六册相关条目及安装主项页；若采用概算候选，给安装已含与独立调试的范围对照。",
     "accepted": "一组安装页＋调试/试验相关页及组台对照，不需要逐条重答是否全带。",
     "already_answered": "除YS7-163外其余全带已经确认；YS7-163排除规则已生成，不列入41条，也不再次询问。",
     "completion": "真实ID及工作内容绑定完成、组台口径明确，防止把已含单体调试重复生成。"},
    {"id": "D08", "title": "电缆和接地土方的源子目及覆盖对照", "rule_ids": ids("A06",96,97,98,99),
     "known": "源YD8-50→YD8-7/13/14、YD9-28→YD8-7均未检得。现概算第7章已含部分挖填/铺砂盖砖，第8章全厂（站）接地含土方、一般深度800mm以内；这些是覆盖依据，不能作旧源编码的替换依据。",
     "request": "沿电力共用确认提供这些源编号的实际册/页、名称、单位和未包含工作范围；若迁移为现概算子目，提供哪些费用已含、哪些确需单列的对应依据。",
     "accepted": "电缆安装、沟土方、铺砂盖砖、接地母线的相关子目与说明页即可；不得只给同名或改前缀后的编号。",
     "already_answered": "R096按50%长度、相关尺寸暂定；0.4/0.3分组末行；源规则中电缆和接地土方分别计取均已答。这里核的是不同计价依据的覆盖差异。",
     "completion": "保留源规则答复；在具体适用子目中核实不重复，不能把概算覆盖说明反向改写已答预算式规则。"},
    {"id": "D09", "title": "第70行埋地防腐保温主工作范围", "rule_ids": ids("A06",70),
     "known": "E70明确埋地管线防腐保温，主量1m、关联补充土方；C70/D70为空且未合并。不能继承67—69行的7-4006～4013主项。",
     "request": "请给本行土方关联针对的主项编号或明确工作范围识别依据；若按防腐保温工作类别关联而不固定编号，请标明这个作用范围及与同沟已有土方的对应。",
     "accepted": "修订表格相应单元格、单行范围说明或已有实施规则的位置。",
     "already_answered": "每1m的0.7×1.8算例为1.26m³已确认，不再询问基数；实际长度、沟宽深取项目资料。",
     "completion": "能够在项目中判断本行是否适用；同时处理D01书名对应，不向上填空。"},
    {"id": "D10", "title": "A09三个星号对象的定义", "rule_ids": ids("A09",11,23,24,25,68),
     "known": "源B11=油气集输-**管线，B23=天然气-**管线且合并至24—25，B68=注水-**管线。现有资料没有**释义；不是解析漏字。",
     "request": "只收取已经存在的修订源表、对象字典或适用范围定义文件及定位，用来补B11/B23/B68的可追溯来源；本轮不要求再次解释这三个**。若尚无这类资料，记录“未取得”并继续阻断，不重开已忽略的A09-04问卷。",
     "accepted": "已有文件路径/页码或既有修订单元格；没有资料时无需新写业务答复。",
     "already_answered": "A09-04历史问题已标红忽略，不重发该问卷；标准化优先、A05第八/九章分流已经确认。本项只补当前源字段对象定义。",
     "completion": "可由项目事实识别对象，而非把**自动当任意通配符；23—25还需D11。"},
    {"id": "D11", "title": "Φ273附近的源区间更正", "rule_ids": ids("A09",23,24,25),
     "known": "D23原文Φ27～Φ273（含168），D24/D25为Φ273以上。区间与括注、边界交集同时存在，现有答复没有给这几格的更正结果。",
     "request": "仅请提供已经存在的区间说明、勘误或修订源表，定位D23/D24/D25的上下限、括注及273mm归属；不要求本轮重新回答原A09-04的边界选择题。未有资料则保留原文和阻断。",
     "accepted": "既有更正记录、区间定义或文件位置；没有资料时无需重答已忽略的问题。",
     "already_answered": "Φ457严格大于、25km含边界、整线分流与缺项借用独立均已答，不再确认。",
     "completion": "判定273及相邻值时只有明确路径；不从别册“以上”的定义跨资料套用。"},
    {"id": "D12", "title": "A09三条空白对象行的归属", "rule_ids": ids("A09",6,87,91),
     "known": "三行仅C列有石油2022概算指标，B/D空且无合并。邻行线索：R006邻R005站外管线；R087邻R086防腐；R091邻R090穿跨越。线索不作为已确认继承。",
     "request": "请分别补三行的对象和触发条件，或明确哪一已存在规则承接此行、此行是否仅说明/重复。可用修订B6/D6、B87/D87、B91/D91表示。",
     "accepted": "一张三行补充表或明确原资料位置，不要求重新编写整张A09。",
     "already_answered": "先标准化后概算、已含防腐不重复、穿越单出图且核实际覆盖均已答；只确认这些空白源行是否及怎样归属。",
     "completion": "三行各有明确去向，不靠邻行位置机械填充，不把通用原则当无条件叠加。"},
]


def build_request(package, source_map, evidence):
    pending = {r["rule_id"]: r for r in package["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    covered = {rid for group in GROUPS for rid in group["rule_ids"]}
    if covered != set(pending) or len(pending) != 41: raise ValueError("materials request must cover exactly the remaining 41")
    reviews = {r["source_record_id"]: r for r in source_map["pending_review"]["records"]}
    records = []
    for rid, row in sorted(pending.items()):
        review = reviews[rid]
        records.append({"rule_id": rid, "groups": [g["id"] for g in GROUPS if rid in g["rule_ids"]],
                        "source_refs": row["source_refs"], "source_values": review["source_values"],
                        "candidate_checks": review["catalog_checks"], "generated_rule_ids": review["generated_rule_ids"],
                        "finding_ids": [f["id"] for f in evidence["findings"] if rid in f["rule_ids"]]})
    return {"schema_version": "0903-materials-request-v1", "release_version": package["release_version"],
            "summary": {"unique_rules": 41, "groups": len(GROUPS), "group_rule_links": sum(len(g["rule_ids"]) for g in GROUPS),
                        "newly_closed": 0, "deferred_0904": 5},
            "existing_evidence": evidence, "groups": GROUPS, "rule_index": records,
            "shared_electricity_request": "D05—D08共用一次版本确认：源表标题为电力概算2018，但YD/YJ/YS源编号未在当前概算库找到；请明确这些源规则原本引用的实际书籍/册、版次和允许库。若本来引用预算，请给对应依据/库；若拟用概算替代，需提供具体子目及包含工作对照，不重复确认已经答过的数量或全带口径。",
            "not_requested": ["已答业务政策", "所有项目的一套默认参数", "0904选价政策/价格表", "重新提供已存在的编号列表", "整套书籍（仅需相关页或明确映射确认）"],
            "handoff": {"resource_version": package["release_version"], "code_base": "SVN根基线r30，混合修订30/47/48/55/59/60；本次未提交；准确工具版本见manifest.tool_inputs SHA-256",
                        "business_server_start": "NOT_REQUIRED_OFFLINE_ONLY", "preview_url": "http://127.0.0.1:18793/",
                        "business_test_url": None, "activation": False}}


def candidate_text(record):
    parts = []
    for check in record["candidate_checks"]:
        lib = check.get("library_code", "")
        selector = check.get("selector", check.get("name_query", check.get("source_code", "")))
        samples = check.get("samples", [])
        if samples:
            parts.append(f"{lib} {selector} → " + " / ".join(f"{x['code']} {x['name']} [{x['unit']}]" for x in samples) + (f"（共{check['count']}项）" if check.get("count", 0)>2 else ""))
        elif check.get("status") == "NOT_RESOLVED_IN_SNAPSHOT": parts.append(f"{lib} {selector}：未检得")
    return "；".join(parts) or "无可据此绑定的子目候选；见源行对象及相邻行线索。"


def markdown_request(data):
    def cell(s): return str(s).replace("|", "\\|").replace("\n", "<br>")
    lines = ["# 0903待补资料清单（41条，按缺失依据归并）", "", f"资源版本：`{data['release_version']}`。本清单是本轮唯一待补资料入口；JSON和网页预览由同一内容生成。",
             "", "**共12组资料，覆盖41条不同规则。** 同一行可能同时缺书名对应、胶片条款或范围，组间有交叉，不能把组内行数相加当作待核条数。已有候选不是已批准映射。当前尚无足以解除具体绑定的新增资料，41条仍阻断；本轮补齐了目录查找方向、包含工作和可核查的候选证据。", "",
             "## 已从项目和当前定额库补齐", "", "数据库使用只读事务重新核查，9个库中没有电力预算2018库；目标五库1,429条目录、11,423条子目与11月10日快照逐条一致。只核查导入副本，未宣称查全正式原书。"]
    for f in data["existing_evidence"]["findings"]:
        lines += ["", f"- **{f['id']}（{'、'.join(f['rule_ids'])}）**：{f['finding']} {f['limit']}"]
    lines += ["", "## 怎样补充", "", "每组提供对应资料或作一次限定范围的确认即可；相同行在多组出现，不需要重答已答业务。无需此刻提供所有项目的长度、重量、检测比例、敷设位置和运输里程。", "", "**电力组共用确认（只回复一次）：**" + data["shared_electricity_request"], "",
              "| 资料编号 | 需要的资料 | 对应规则行 |", "|---|---|---|"]
    for g in data["groups"]: lines.append(f"| [{g['id']}](#{g['id']}) | {g['title']} | {'、'.join(g['rule_ids'])} |")
    for g in data["groups"]:
        lines += ["", f"<a id=\"{g['id']}\"></a>", f"## {g['id']}　{g['title']}", "", "**对应规则：**" + "、".join(g["rule_ids"]), "",
                  "**已有依据/候选：**"+g["known"], "", "**请提供或确认：**"+g["request"], "", "**可接受的最小资料：**"+g["accepted"], "",
                  "**已答，不再询问：**"+g["already_answered"], "", "**收到后的处理：**"+g["completion"]]
    lines += ["", "## 41条逐行索引及已有候选", "", "真实候选ID、源单元格及查询细节保存在同版materials-request.json；下表仅作阅读摘要。", "",
              "| 规则行 | 资料组 | 原主项→目标/对象 | 已有候选（不自动绑定） | 本轮补证 |", "|---|---|---|---|---|"]
    for r in data["rule_index"]:
        v = r["source_values"]
        main = v.get("main_code") or v.get("subject") or (v["main_name"] + "（主项编号空）" if v.get("main_name") else "空白对象")
        source = main + " → " + v.get("related_code", v.get("target_code", v.get("target_name", v.get("target", "补充项目"))))
        lines.append("| " + " | ".join(cell(x) for x in [r["rule_id"], "、".join(r["groups"]), source, candidate_text(r), "、".join(r["finding_ids"]) or "源/答复核对，无新绑定证据"]) + " |")
    lines += ["", "## 回复模板", "", "```text", "资料编号：D__（可一次覆盖多组）", "资料或确认内容：", "适用库代码/书名/版次及规则行：", "原文位置：册/章/页/条目，或已有项目文件路径", "适用范围与例外：", "```", "",
              "收到资料后，由实施方补正式ID、出处和范围，生成新版本并重跑边界/防重验收。不能直接修改v1/v2/v3或将阻断布尔值改成true。0904仍在后续；已答问题台账不重新打开。", "",
              "## 交接", "", "- 代码/资源版本："+data["handoff"]["code_base"]+"；资源`"+data["release_version"]+"`。", "- 修改文件、启动命令、测试地址、用例和实际结果见[交接与验收](../../../../verification-evidence/pending-materials-20261112/交接与验收.md)。", "- 本次仅离线规则资源、证据和文档；无业务部署或业务测试地址。预览地址为`http://127.0.0.1:18793/`，只监听本机，服务未运行时按交接命令启动；本轮真实界面验证受环境策略阻断，状态见交接说明。", ""]
    return "\n".join(lines)


def html_preview(data):
    groups = []
    for g in data["groups"]:
        body = "".join(f"<p><strong>{label}</strong> {escape(g[key])}</p>" for label,key in [("已有依据/候选：","known"),("请提供或确认：","request"),("最小资料：","accepted"),("已答，不再询问：","already_answered"),("收到后的处理：","completion")])
        groups.append(f'<section id="{g["id"]}" class="group"><h2>{g["id"]} · {escape(g["title"])}</h2><p class="rows">{escape("、".join(g["rule_ids"]))}</p>{body}</section>')
    rows = "".join(f'<tr><td>{r["rule_id"]}</td><td>{" / ".join(r["groups"])}</td><td>{escape(candidate_text(r))}</td></tr>' for r in data["rule_index"])
    findings = "".join(f'<li><strong>{f["id"]}</strong> {escape(f["finding"])} {escape(f["limit"])}</li>' for f in data["existing_evidence"]["findings"])
    nav = "".join(f'<a href="#{g["id"]}">{g["id"]}</a> ' for g in data["groups"])
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0903待补资料清单 · 41条</title>
<style>body{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;background:#f5f7fa;color:#1c2b3a;margin:0}main{max-width:1100px;margin:auto;padding:32px}h1{font-size:28px}h2{font-size:21px}header,.group,.index{background:white;border:1px solid #dae3ec;border-radius:12px;padding:24px;margin:18px 0}.rows{color:#345d85;overflow-wrap:anywhere}.badge{padding:8px 14px;display:inline-block;background:#e9f0fb;margin:5px;border-radius:8px}a{color:#1259a5}nav a{display:inline-block;margin-right:13px}input{font:inherit;padding:12px;width:min(95%,620px);border:1px solid #a2b5c8;border-radius:7px}.group p{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border:1px solid #dce3eb;text-align:left;vertical-align:top}td:last-child{overflow-wrap:anywhere}.hint{color:#536477}.index{overflow-x:auto}section{scroll-margin-top:20px}@media(max-width:600px){main{padding:12px}header,.group,.index{padding:15px}}</style>
<main><header><h1>0903待补资料清单</h1><p>''' + escape(data["release_version"]) + ''' · 同源只读预览</p><span class="badge">41条不同规则</span><span class="badge">12组资料</span><span class="badge">0904保留后续</span><p>当前41条仍阻断。组间有交叉，不将分组行数相加；已答业务不重复提问。</p><nav>''' + nav + '''</nav><p><label for="search">查找资料组或规则行</label><br><input id="search" placeholder="例如 A06-R069、胶片、D02"><span id="count" aria-live="polite">12 / 12 组</span></p><p class="hint">这是资料清单预览，不连接业务服务、不保存回复。完整版本以同版Markdown/JSON为准。</p></header><section class="index"><h2>本轮已核实</h2><ul>''' + findings + '''</ul><p><strong>电力组只需一次共用确认：</strong>''' + escape(data["shared_electricity_request"]) + '''</p></section>''' + "".join(groups) + '''<section class="index"><h2>41条逐行索引</h2><table><thead><tr><th>规则行</th><th>资料组</th><th>已有候选</th></tr></thead><tbody>''' + rows + '''</tbody></table></section></main><script>const search=document.querySelector('#search');function filterGroups(){const q=search.value.trim().toLowerCase();let n=0;document.querySelectorAll('.group').forEach(s=>{const yes=s.textContent.toLowerCase().includes(q);s.hidden=!yes;if(yes)n++});document.querySelector('#count').textContent=`${n} / 12 组`;}search.addEventListener('input',filterGroups);document.querySelectorAll('nav a').forEach(a=>a.addEventListener('click',()=>{search.value='';filterGroups();}));</script></html>'''
