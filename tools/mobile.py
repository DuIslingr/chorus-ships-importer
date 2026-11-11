"""The phone version of the built mod (import.py --mobile), as the ES2 importer makes its own: the same mod id (saves move
between devices), " (phone)" in its name, in <out>_phone and zipped for the game's Mods > Import mod.

- The static models decimated in Blender (tools/decimate_blender.py) to `ratio` of their triangles (none below MIN_TRIS):
  the stations, the rocks and the NPC hulls without animations. The rest as built: the player ships, the rigged and
  skinned NPCs (their bones and clips must stay), the weapons and turrets (their marker nodes must stay exactly).
- Every image halved, but those read texel by texel or row by row: Chorus's palettes (maps/chorus/pal_*: ChorusLayers
  loads its swatch by UV set 3) and the planets' curve rows (planets/*_curves.png).
"""
import json, os, shutil, subprocess, zipfile
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TRIS = 400
DECIMATE_FOLDERS = ('models/stations', 'models/rocks')
EXACT = (lambda rel: os.path.basename(rel).startswith('pal_') and rel.startswith('maps/chorus/'),
         lambda rel: rel.startswith('planets/') and rel.endswith('_curves.png'))
SKIP_IN_ZIP = ('.DS_Store', 'Thumbs.db', 'desktop.ini', '__MACOSX')


def _static_npcs(mod):
    """The NPC hulls with no animation of their own (ships.json: no "animations", not "skinned")."""
    path = os.path.join(mod, 'ships.json')
    if not os.path.exists(path): return []
    return [e['model'] for e in json.load(open(path, encoding='utf-8'))
            if e.get('model', '').startswith('models/npc/') and not e.get('animations') and not e.get('skinned')]


def decimate_list(mod):
    out = []
    for folder in DECIMATE_FOLDERS:
        d = os.path.join(mod, folder)
        if os.path.isdir(d): out += [f'{folder}/{f}' for f in sorted(os.listdir(d)) if f.endswith('.glb')]
    return out + [m for m in _static_npcs(mod) if os.path.exists(os.path.join(mod, m))]


def make_mobile(mod, out, ratio, blender):
    if os.path.exists(out): shutil.rmtree(out)
    shutil.copytree(mod, out)
    info = json.load(open(os.path.join(mod, 'mod.json'), encoding='utf-8-sig'))
    info['name'] = info.get('name', 'Chorus Ships') + ' (phone)'
    json.dump(info, open(os.path.join(out, 'mod.json'), 'w', encoding='utf-8'), indent=1)
    halved = kept = 0
    for d, _, names in os.walk(out):
        for n in names:
            if not n.lower().endswith('.png'): continue
            full = os.path.join(d, n)
            rel = os.path.relpath(full, out).replace(os.sep, '/')
            if rel.startswith('icons/') or rel == 'preview.png' or any(f(rel) for f in EXACT): kept += 1; continue
            im = Image.open(full)
            if im.size[0] <= 8 or im.size[1] <= 8: continue
            im.resize((max(4, im.size[0] // 2), max(4, im.size[1] // 2)), Image.LANCZOS).save(full, optimize=True)
            halved += 1
    print(f'  phone: {halved} images halved, {kept} kept as they are')
    files = decimate_list(mod)
    if files:
        if not blender: raise SystemExit('--mobile needs Blender (4.2 or newer) to decimate the models: give its path with --blender')
        lst = os.path.join(out, '.decimate_list.txt')
        open(lst, 'w').write('\n'.join(files) + '\n')
        print(f'  phone: decimating {len(files)} models in Blender (to {ratio:.0%} of their triangles; this takes a while)...')
        subprocess.run([blender, '-b', '--factory-startup', '--python-exit-code', '1', '-P',
                        os.path.join(HERE, 'tools', 'decimate_blender.py'), '--', lst, mod, out, str(ratio), str(MIN_TRIS)], check=True)
        os.remove(lst)
    return out


def zip_folder(folder, zip_path):
    """The folder as a zip for the game's Import mod (fixed dates: the same build gives the same zip)."""
    if os.path.exists(zip_path): os.remove(zip_path)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for base, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_IN_ZIP and not d.startswith('.'))
            for f in sorted(files):
                if f in SKIP_IN_ZIP or f.startswith('._') or f.startswith('.'): continue
                full = os.path.join(base, f)
                info = zipfile.ZipInfo(os.path.relpath(full, folder).replace(os.sep, '/'), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                with open(full, 'rb') as src, zf.open(info, 'w', force_zip64=True) as dst:
                    shutil.copyfileobj(src, dst)
    return zip_path
