import json, re, html
from pathlib import Path

base = Path(__file__).resolve().parent.parent / 'Workflow_slim_22_nodes'
dest = Path(__file__).resolve().parent
# Read every source file, including validation programs and all examples.
files = {str(p.relative_to(base)).replace('\\','/'): p.read_text(encoding='utf-8') for p in sorted(base.rglob('*')) if p.is_file()}
inv = json.loads(files['workflow-node-inventory.json'])
guide = files['07-Workflow逐节点配置参考.md']
rows = {}
for line in guide.splitlines():
    m = re.match(r'^\| `([^`]+)` · ([^|]+)\|', line)
    if m and m.group(1) in {x['id'] for x in inv['nodes']}:
        rows[m.group(1)] = [re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', x.strip()) for x in line.strip('|').split('|')]
prompts = {}
prompts['sLLM'] = files['04-模型-System.md'].split('---',1)[1].strip()
cbs = files['05-CBS两轮匹配提示词.md']
blocks = re.findall(r'```text\s*\n(.*?)\n```', cbs, re.S)
prompts['qCbsLeafLLM'], prompts['qCbsParentLLM'] = blocks
data = {'inventory':inv, 'rows':rows, 'prompts':prompts, 'files':files}
payload = json.dumps(data, ensure_ascii=False).replace('</','<\\/')
template = (dest/'template.html').read_text(encoding='utf-8')
(dest/'index.html').write_text(template.replace('/*__DATA__*/', 'const DATA = '+payload+';'), encoding='utf-8')
print('Built index.html; files:', len(files), 'nodes:',len(inv['nodes']), 'edges:',len(inv['normal_and_business_branch_edges']), 'node rows:',len(rows))
