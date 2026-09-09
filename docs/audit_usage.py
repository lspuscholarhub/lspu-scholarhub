"""One-shot audit: find templates, routes, model fields, and service functions
that are never used anywhere in the codebase. Read-only — run and discard.
"""
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BS = chr(92)

py_code = ''
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            py_code += open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()

tmpl_code = ''
for r2, d2, fs2 in os.walk('app/templates'):
    for f2 in fs2:
        if f2.endswith('.html'):
            tmpl_code += open(os.path.join(r2, f2), encoding='utf-8', errors='ignore').read()

# ── 1. Templates never rendered NOR extended/included ────────────────────────
orphans = []
for root, dirs, files in os.walk('app/templates'):
    for f in files:
        if not f.endswith('.html'):
            continue
        rel = os.path.relpath(os.path.join(root, f), 'app/templates').replace(BS, '/')
        if rel == 'base.html':
            continue  # extended by every page
        if (f"'{rel}'" not in py_code and f'"{rel}"' not in py_code
                and rel not in tmpl_code.replace(f'{{% extends "{rel}" %}}', '')):
            orphans.append(rel)
print('=== Templates never rendered, extended, or included ===')
print('\n'.join(orphans) if orphans else '(none)')

# ── 2. Routes never linked/redirected from anywhere ──────────────────────────
route_defs = []
for vf in sorted(os.listdir('app/views')):
    if not vf.endswith('.py') or vf == '__init__.py':
        continue
    bp = vf[:-3]
    src = open(f'app/views/{vf}', encoding='utf-8', errors='ignore').read()
    for m in re.finditer(r"def (\w+)\(", src):
        route_defs.append(f'{bp}.{m.group(1)}')

all_code = py_code + tmpl_code
unlinked = []
for ep in route_defs:
    if f"url_for('{ep}'" in all_code or f'url_for("{ep}"' in all_code:
        continue
    # also catch endpoint references in JS-like strings e.g. data-url="/staff/x"
    unlinked.append(ep)
print()
print('=== Route endpoints never referenced via url_for() ===')
print('\n'.join(unlinked) if unlinked else '(none)')

# ── 3. Model columns never referenced outside their own model file ───────────
print()
print('=== Model columns never referenced outside their defining module ===')
model_dir = 'app/models'
for mf in sorted(os.listdir(model_dir)):
    if not mf.endswith('.py') or mf == '__init__.py':
        continue
    src = open(os.path.join(model_dir, mf), encoding='utf-8', errors='ignore').read()
    for m in re.finditer(r'^\s{4}(\w+)\s*=\s*db\.Column', src, re.M):
        col = m.group(1)
        if col in ('id', 'created_at', 'updated_at'):
            continue
        # count references in the rest of the codebase
        uses = len(re.findall(rf'\.{col}\b', py_code.replace(src, ''))) + \
               len(re.findall(rf"{col}\s*=", tmpl_code))
        if uses == 0:
            print(f'  {mf}: {col}')

# ── 4. Service public functions never called outside their own module ───────
print()
print('=== Service functions never called from outside their module ===')
svc_dir = 'app/services'
for sf in sorted(os.listdir(svc_dir)):
    if not sf.endswith('.py') or sf == '__init__.py':
        continue
    src = open(os.path.join(svc_dir, sf), encoding='utf-8', errors='ignore').read()
    others = py_code.replace(src, '')
    for m in re.finditer(r'^def (\w+)\(', src, re.M):
        fn = m.group(1)
        if fn.startswith('_'):
            continue
        if not re.search(rf'\b{fn}\(', others):
            print(f'  {sf}: {fn}()')
