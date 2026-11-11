#!/usr/bin/env python3
"""A contact sheet of every ship in the built mod: one render each (tools/sheet_blender.py), in a labelled grid with each
ship's name, length in metres and role (sold where / flown by which traffic); and the same by role on pages of a dozen
at most, larger (<out>_player / _fighters / _bosses / _freighters_<n> / _capital .png).

    python3 tools/sheet.py [--mod chorus_ships] [--out chorus_ships_sheet.png] [--blender blender] [--weapon <glb in the mod>]
"""
import argparse, json, os, shutil, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIT = 0.05   # remake metres per game unit
RACES = {0: 'Terran', 1: 'Vossk', 2: 'Nivelian', 3: 'Midorian', 8: 'pirates', 9: 'Void'}


def role(s):
    t = s.get('traffic')
    if isinstance(t, dict) and t.get('boss'): return 'pirate boss'
    if isinstance(t, dict) and t.get('capital') == 'freighter': return 'freighter'
    if isinstance(t, dict) and t.get('capital'): return 'capital ship, ' + RACES.get(s.get('race'), str(s.get('race')))
    if isinstance(t, dict): return 'traffic: ' + ', '.join(RACES.get(r, str(r)) for r in t.get('races', []))
    if s.get('lounge'): return f"lounge, {s['price'] / 1e6:.1f} M"
    return 'not sold'


def length_m(s, kits, mod):
    if 'modelLength' in s: return s['modelLength'] * UNIT
    k = kits.get(s.get('kit'))
    if not k: return None
    import sys; sys.path.insert(0, HERE)
    from tools import glb
    part = next(p for p in k['parts'] if p['id'] == s.get('build', {}).get('hull', k['parts'][0]['id']))
    lo, hi = glb.bounds(glb.static_mesh(os.path.join(mod, part['model'])))
    return float(max(hi - lo)) * k.get('scale', 1.0)


_names = os.path.join(HERE, 'chorus_work', 'names.json')   # (npcs.names: where each NPC ship's name came from)
SOURCES = json.load(open(_names)) if os.path.exists(_names) else {}
GROUPS = [('player', 'ships the player flies'), ('fighters', 'fighters in the traffic'), ('bosses', 'pirate bosses'),
          ('freighters', 'freighters'), ('capital', 'capital ships')]


def group_of(s):
    t = s.get('traffic') if isinstance(s.get('traffic'), dict) else {}
    if s.get('lounge') or not t: return 'player'
    if t.get('boss'): return 'bosses'
    if t.get('capital') == 'freighter': return 'freighters'
    if t.get('capital'): return 'capital'
    return 'fighters'


def page(ships, tmp, lengths, out, title, cols, cw, ch, cap=70):
    rows = (len(ships) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, rows * (ch + cap) + 90), (14, 15, 19))
    d = ImageDraw.Draw(sheet)
    d.text((24, 22), f'Chorus Ships (chorus_ships_importer): {title}', font=font(34), fill=(235, 235, 240))
    big = cw >= 800
    for i, s in enumerate(ships):
        x, y = (i % cols) * cw, 90 + (i // cols) * (ch + cap)
        p = os.path.join(tmp, s['id'] + '.png')
        if os.path.exists(p):
            im = Image.open(p).convert('RGBA').resize((cw, ch), Image.LANCZOS); sheet.paste(im, (x, y), im)
        n = lengths.get(s['id'])
        d.text((x + 20, y + ch + 4), s['name'], font=font(30 if big else 26), fill=(240, 240, 245))
        src = SOURCES.get(s['id'])
        info = ' · '.join(v for v in ((f'{n:.0f} m' if n else ''), role(s), ('kit ship' if s.get('kit') else ''),
                                      ({'Chorus': "Chorus's name", 'asset': 'named by its asset', 'importer': 'our name'}.get(src, ''))) if v)
        d.text((x + 20, y + ch + (40 if big else 36)), info, font=font(20 if big else 18), fill=(150, 160, 175))
    sheet.save(out, optimize=True)


def font(size):
    for f in ('/usr/share/fonts/TTF/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf'):
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mod', default=os.path.join(HERE, 'chorus_ships'))
    ap.add_argument('--out', default=os.path.join(HERE, 'chorus_ships_sheet.png'))
    ap.add_argument('--blender', default=shutil.which('blender'))
    ap.add_argument('--weapon', default='models/weapons/sk_gatlingt2a.glb', help='the weapon model shown on the kit ships')
    a = ap.parse_args()
    ships = json.load(open(os.path.join(a.mod, 'ships.json'), encoding='utf-8'))
    kits = {k['id']: k for k in json.load(open(os.path.join(a.mod, 'shipkits.json')))} if os.path.exists(os.path.join(a.mod, 'shipkits.json')) else {}
    with tempfile.TemporaryDirectory() as tmp:
        weapon = a.weapon if os.path.exists(os.path.join(a.mod, a.weapon)) else ''
        subprocess.run([a.blender, '-b', '--factory-startup', '-P', os.path.join(HERE, 'tools', 'sheet_blender.py'), '--', a.mod, tmp, weapon],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lengths = {s['id']: length_m(s, kits, a.mod) for s in ships}
        page(ships, tmp, lengths, a.out, 'every ship in the mod', 4, 600, 390)   # the whole fleet, small
        # and by role, a dozen at most a page, larger (<out>_<group>[_<n>].png)
        base = os.path.splitext(a.out)[0]
        for key, title in GROUPS:
            group = [s for s in ships if group_of(s) == key]
            for n in range(0, len(group), 12):
                part = f'_{n // 12 + 1}' if len(group) > 12 else ''
                page(group[n:n + 12], tmp, lengths, f'{base}_{key}{part}.png', title + (f' ({n // 12 + 1})' if part else ''), 3, 800, 520)
    print(f'{len(ships)} ships -> {a.out}')


if __name__ == '__main__':
    main()
