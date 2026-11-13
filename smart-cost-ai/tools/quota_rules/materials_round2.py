"""Second-round material follow-up; v3/v4 historical renderers remain intact."""
from copy import deepcopy

from materials_request import candidate_text
from materials_followup import html_followup


def build_round2(package, source_map, evidence, confirmations, previous):
    pending = {r['rule_id']: r for r in package['pending_rules'] if r['pending_kind'] == 'TECHNICAL_EVIDENCE'}
    reviews = {r['source_record_id']: r for r in source_map['pending_review']['records']}
    before = {r['rule_id'] for r in previous['rule_index']}
    closed = sorted(before - set(pending))
    if set(pending)-before or closed != confirmations['expected_newly_closed_rule_ids']:
        raise ValueError('unexpected second-round closure')
    groups = deepcopy(previous['groups'])
    answers = {
        'D02':'已采纳用户限定确认：DE06000003承载指南安装估价表，仅限本组7行。真实子目已绑定；源刊名与库名分别保留，不声明出版物完全相同；设计重量和子方阵分组仍是项目输入。',
        'D03':'①限定确认F-b4及R078—081，实际台数/运距和原企业参数保留；②撤销R072/073风电分支保持。排除升压站及35kV以上输电线路不等于全部35kV以下都适用。',
        'D04':'已选择设计/检测方案明确胶片规格和数量，编译明确目标分支；缺少项目证据、壁厚或唯一明确目标继续待补。原书自动选片条款未核，不使用DN100/8mm示例阈值。',
        'D05':'已答保留R21电力分支待补；4-3202只用于原R18—R20三库，不将三库同号证据用于关闭R21，不自动换库。',
        'D06':'已答保留YD2-20→YD2-91，按设计实际油量t；不采用GD2-13。概算工作内容含油过滤不能证明预算YD2-20也含，预算重复工作判断仍需原页。',
        'D07':'保留预算YJ16-2及七个YS关联；GJ14-2的名称/台单位不能证明组=台或工作内容相同。不用概算候选替换。',
        'D08':'已答保留电力预算四行，原已答长度比例和几何口径保留；不以4-3141/3143统一替换，不将概算已含土方结论套到预算。'}
    for g in groups:
        gid = g['id']
        g['pending_rule_ids'] = [r for r in g['rule_ids'] if r in pending]
        if gid in answers:g['answer']=answers[gid]
        if not g['pending_rule_ids']:
            g.update(status='CLOSED',request='无需补充或重复确认。',accepted='已记录的限定确认及项目输入合同。',completion=g['answer'])
        else:g['status']='OPEN'
        if gid in answers:g['already_answered'] += '；第二轮：' + answers[gid]
        if gid == 'D05':
            g.update(known='原A05 R18/R19/R20分别为石油/光伏/风电4-3202，原R21为独立电力2018分支。现电力概算第7章仅证明厂站内35kV及以上转预算第五册；R21真实电力目标尚未核实。附件1425基价不在冻结目录字段内，本轮不作价格已核声明。',
                     request='提供适用于该35kV、3×95mm²样例实际敷设位置的正式电力子目页与适用说明，含编号、名称、单位、书名版次及册章定位。若为厂站内，按已核条款查预算2018第五册；若为站外或位置尚未明确，先核适用条款及真实册章，不预判都在第五册、不自动换库。敷设位置是具体项目输入。保留电力依据的选择已答，不再要求换库确认。',
                     accepted='相应正式子目页＋章说明/适用范围页；无需重复给石油4-3202。',completion='核对电力编号/单位/范围后限定绑定，不机械改YD/GD前缀。')
        if gid == 'D06':
            g.update(known='源A06 R87仅YD2-20→YD2-91。现概算候选GD2-13含油过滤，但不能判断预算YD2-20是否已含；用户已明确不替换。实际设计油量t口径保持。',
                     request='提供电力预算2018相关册YD2-20与YD2-91子目页、单位及工作内容/章说明，用于确认两项身份及油过滤是否重复。无需再选择概算候选。',
                     accepted='两个预算子目页＋可判断油过滤覆盖关系的说明页。',completion='保持预算分项，在真实子目与覆盖关系核实后决定是否关联；不让GD2-13使现有实际油量口径作废。')
        if gid == 'D07':
            g['known']='现概算GJ14-2为300Mvar空冷调相机、单位台。源主项YJ16-2单位组；YS5-196、YS6-53、YS6-57、YS7-164/166/167/168各台。原1组→1台算例不足以证明工程对象/工作覆盖等同。'
            g['request']='仍需预算2018第二册YJ16-2安装项及第六册七个YS调试项正式页（编号、名称、单位、工作内容及计量说明），确认组/台对应和防重复。已排除YS7-163不重开。'
        if gid == 'D08':
            g.update(known='R96—98主项YD8-50，关联YD8-7土方m³、YD8-13/14铺砂盖砖100m；R99主项YD9-28接地扁钢，关联YD8-7。概算库已含相应工作不证明预算也含；石油4-3141/3143（100m）不能直接替换预算m³关系。',
                     request='提供预算2018相应册/章中YD8-50、YD8-7、YD8-13、YD8-14及YD9-28各自对应的正式子目页与工作内容/章说明，核实每个编号的册章定位、主项是否已含土方/铺砂盖砖及单位。不能从厂站内35kV及以上的第五册指向推定这些源编号也在第五册。保留预算的选择已答，不再索要石油替换确认。',
                     accepted='上述主项/关联项正式页＋包含/另计说明；此前长度比例和几何答复无需重答。',completion='在预算原依据内核编号、单位和工作覆盖，保留原几何及长度比例参数，不跨库补编号。')
    index=[]
    for rid,row in sorted(pending.items()):
        r=reviews[rid]
        index.append(dict(rule_id=rid,groups=[g['id'] for g in groups if rid in g['pending_rule_ids']],
                          source_refs=row['source_refs'],source_values=r['source_values'],candidate_checks=r['catalog_checks'],
                          generated_rule_ids=r['generated_rule_ids'],missing_evidence=r['missing_evidence'],pending_scope=row['conservative_scope']))
    return dict(schema_version='0903-materials-request-v3',release_version=package['release_version'],
                summary=dict(baseline_unique_rules=len(before),unique_rules=len(pending),groups=12,
                             active_groups=sum(bool(g['pending_rule_ids']) for g in groups),group_rule_links=sum(len(g['pending_rule_ids']) for g in groups),newly_closed=len(closed),deferred_0904=5),
                baseline_rule_ids=sorted(before),newly_closed_rule_ids=closed,groups=groups,rule_index=index,
                existing_evidence=evidence,confirmed_changes=confirmations,
                shared_electricity_request='D05/D06/D08已明确保留电力原依据；共用正式书名、版次、册/章定位资料提供一次即可，逐项子目及覆盖页仍需对应，不能用概算GD/GJ/GS或石油同名项替代预算YD/YJ/YS。',
                scope_note='本次14行按限定用途闭合；18行仍缺技术依据，0904五行后续；运行时的设计缺参不伪装成规则已自动选片。')


def markdown_round2(data):
    def cell(v): return str(v).replace('|','\\|').replace('\n','<br>')
    s=data['summary']
    lines=['# 0903第二轮资料跟进清单','',f"版本：`{data['release_version']}`。技术待核32→18条，本轮14行按限定用途闭合；原12组中6组仍需资料，共21处待补关联（D10/D11重叠3行）。0904仍5条后续。",'',
           'D02/D03只是限定项目库映射，未证明全库出版物同一；D04仅接受有依据的明确选片。D05/D06/D08保留原电力依据，不跨库闭合。','',
           '本轮闭合：'+'、'.join(data['newly_closed_rule_ids']),'','## 12组处理结果','',
           '| 组 | 当前状态 | 待补规则行 | 已处理 |','|---|---|---|---|']
    for g in data['groups']:
        lines.append('| '+' | '.join(cell(v) for v in [g['id']+' '+g['title'],'已答，无需补充' if g['status']=='CLOSED' else '仍缺技术资料','、'.join(g['pending_rule_ids']) or '—',g['answer']])+' |')
    lines+=['','## 尚缺资料','',data['shared_electricity_request']]
    for g in data['groups']:
        if not g['pending_rule_ids']:continue
        lines+=['',f"### {g['id']} {g['title']}",'','对应行：'+'、'.join(g['pending_rule_ids']),'','已有候选：'+g['known'],'','需要补充：'+g['request'],'','最小资料：'+g['accepted'],'','已答，不再询问：'+g['already_answered'],'','闭合条件：'+g['completion']]
    lines+=['','## 18条逐行索引','','| 规则行 | 资料组 | 尚缺依据 | 已有候选 |','|---|---|---|---|']
    for r in data['rule_index']:
        lines.append('| '+' | '.join(cell(v) for v in [r['rule_id'],'、'.join(r['groups']),'；'.join(r['missing_evidence']),candidate_text(r)])+' |')
    lines+=['','D10/D11只收已有更正资料，无资料继续待补，不重开已忽略问卷。所有旧原表、旧答复及v1—v4发布目录保留。',
            '', '[代码版本、修改文件、启动方式、测试地址、测试用例和预期结果](../../../../verification-evidence/materials-confirmation-20261112-v5/交接与验收.md)。本轮仅离线资源；在线0903及0904未实施。','']
    return '\n'.join(lines)


def html_round2(data):
    return html_followup(data).replace('41→','32→').replace('32条待补索引','18条待补索引')
