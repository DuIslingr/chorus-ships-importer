"""Chorus's Rites (Nara's powers) as remake devices (items.json, device 23+, paid from the ship's Rite energy: the remake's
Flight.RiteEnergy, Chorus's EnergyComponent of 3 pips at 0.22 a second).

Read from BP_PowersMasterData (names, texts, icons) and the BP_ActivePower_* defaults:
- Rite of the Hunt (BP_ActivePower_Blink: Range 100000 cm, BlinkLocationOffset -18000 cm, EnergyCost 2, Cooldown 0.5)
  -> device 23. Its range and landing are left at 0, so the remake scales Chorus's (1000 m and 180 m at its 140 m/s)
  with the ship's own top speed, as its Chorus flight does.

Each Rite's shop icon is its powers-screen icon (T_Powers_Power<N>_Icn, 264 x 264) on a plate drawn like the game's (180 x
88: a slanted, striped frame). Pulse Zap, Drill, Telekinesis, Scan and the passives are still to come in the remake.
"""
import os

ICONS = 'SpacePrototype/Content/UnleashedPrototype/GUI/Art/Iconography/Powers/'
# (id, Chorus's PowerName, name, description, its powers-screen icon, stats)
RITES = [
    ('chorus_rite_hunt', 'Blink', 'Rite of the Hunt',
     "Within the blink of an eye, leap onto the tail of the hostile ship in your sights (your lock first), facing the way it "
     "flies. Pays 2 of your 3 pips of Rite energy, which grow back one every 4.5 s. Not at capital ships. (Chorus)",
     'T_Powers_Power2_Icn', {'cabinSize': 0, 'device': 23, 'deviceRiteCost': 2, 'deviceCooldownMs': 500}),
]

EXPORTS = [ICONS + r[4] for r in RITES]


def _plate(w=180, h=88):
    """The game's shop plate: a parallelogram with slanted ends, dark and see-through, with diagonal stripes."""
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    mask = Image.new('L', (w, h), 0)
    s = 14   # the slant
    ImageDraw.Draw(mask).polygon([(s, 2), (w - 1, 2), (w - 1 - s, h - 3), (0, h - 3)], fill=255)
    fill = Image.new('RGBA', (w, h), (18, 30, 44, 150))
    stripes = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(stripes)
    for x in range(-h, w + h, 22):
        d.polygon([(x, h), (x + 11, h), (x + 11 + h, 0), (x + h, 0)], fill=(70, 96, 120, 60))
    fill.alpha_composite(stripes)
    img.paste(fill, (0, 0), mask)
    return img


def _icon(src, dst):
    from PIL import Image
    plate = _plate()
    orb = Image.open(src).convert('RGBA').resize((92, 92), Image.LANCZOS)
    plate.alpha_composite(orb, ((plate.width - orb.width) // 2, (plate.height - orb.height) // 2))
    plate.save(dst, optimize=True)


def items(export, out):
    """items.json entries for the Rites; their icons into <out>/icons/ (none without the export or PIL: the cabin's)."""
    result = []
    for rid, _, name, desc, icon, stats in RITES:
        it = {'id': rid, 'base': 91, 'name': name, 'description': desc, 'techLevel': 9, 'occurrence': 2,
              'price': [250000, 262000], 'stats': dict(stats)}
        src = os.path.join(export, ICONS + icon + '.png')
        if os.path.exists(src):
            try:
                os.makedirs(os.path.join(out, 'icons'), exist_ok=True)
                _icon(src, os.path.join(out, 'icons', rid + '.png'))
                it['icon'] = f'icons/{rid}.png'
            except ImportError:
                pass
        result.append(it)
    return result
