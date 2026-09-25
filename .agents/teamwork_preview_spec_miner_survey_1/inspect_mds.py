import json
import re

with open(r'c:\Users\admin\Downloads\NGO AI LLM\Aasha-AI\chapters\RationalNumbers_Class8_MDS.html', 'r', encoding='utf-8') as f:
    content = f.read()

print('MDS HTML length:', len(content))
m = re.search(r'var NODES\s*=\s*(\[.*?\]);\s*var App', content, re.DOTALL)
if m:
    nodes = json.loads(m.group(1))
    print('NODES count in MDS:', len(nodes))
    for i, n in enumerate(nodes):
        title = n.get('title', 'No Title')
        steps = n.get('steps', [])
        print(f"Node {i+1}: {title} (steps: {len(steps)})")
        for s_idx, s in enumerate(steps):
            stype = s.get('t', '')
            stitle = s.get('title', '')
            sq = s.get('q', '')
            if isinstance(sq, dict):
                sq = sq.get('q', '')
            print(f"   Step {s_idx+1}: [{stype}] {stitle} | {str(sq)[:80]}")
else:
    print('NODES pattern not matched directly')
