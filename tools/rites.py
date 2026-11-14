"""Chorus's Rites (Nara's powers) as remake devices (items.json, device 23+, paid from the ship's Void energy: the remake's
Flight.VoidEnergy, Chorus's EnergyComponent of 3 pips at 0.22 a second, its regrowth on Void Crystals).

Read from BP_PowersMasterData (names, texts, icons) and the BP_ActivePower_* defaults:
- Rite of the Hunt (BP_ActivePower_Blink: Range 100000 cm, BlinkLocationOffset -18000 cm, EnergyCost 2, Cooldown 0.5)
  -> device 23. Its range and landing are left at 0, so the remake scales Chorus's (1000 m and 180 m at its 140 m/s)
  with the ship's own top speed, as its Chorus flight does.
- Rite of the Storm (BP_ActivePower_Pulse_Zap: Range 100000 cm, ShieldDamage 300, EnergyCost 2, Cooldown 0.5; BP_Buff_Pulse:
  a 4 s jam) -> device 24: 150 off the shield (Chorus's 300 at the remake's hull share, x 0.5, as the capital ship's
  weapons), an NPC without a shield (the game's) half of that on its hull; the chain is upgrade A's, not taken.
- Rite of the Star (BP_ActivePower_Drill on ADrillActivePower: EnergyCost 3, CollisionDamage 750 every 0.2 s, MaxDurationTime
  3) -> device 25: 375 a tick (750 at the hull share); its speed, turn and reach are the remake's (Chorus's, by the top speed).
- Rite of Control (BP_ActivePower_Telekinesis: GrabRange 70000, TossRange 80000, TossSpeed 56000 cm/s, EnergyCost 3;
  BP_Telekinesis_Debuff: CollisionDamageOtherTargets 500) -> device 26: 250 to the ship it is thrown into, held 8 s at most.
- Rite of the Senses (BP_ActivePower_Scan's short range: ShortRangeScanDistance 600000 cm over 3 s; the powers screen's cost
  1) -> device 27: cloaked ships and containers uncovered, the Ultrascan's sight for 20 s; held, the long range (the orbit).

Their looks (items.json fx "rite", the remake's Data.CustomRiteFx: fx/rite_<id>.json) are Chorus's own: the Cascade particle
systems the blueprints spawn, converted by tools/explosions.py's emitter reader with each material's image (LOOKS'
materials: the flares, lens flares and lines their textures white on black, the glows a soft disc, the barrier smoke its
emissive flipbook added, the black ink dark and alpha-blended; the refraction, the radial force and the mesh tendrils
left out); the hit's looping emitters repeated over the jam. The sounds are their FMOD events (the start the fx's "shot");
an event's layers (waves of different names: Blink_Start's low hit and whoosh) mixed into one file, its variations (the
same name numbered: Pulse_Muzzle's four thunder bolts) kept as a random pick.

Each Rite's shop icon is its powers-screen icon (T_Powers_Power<N>_Icn, 264 x 264) on a plate drawn like the game's (180 x
88: a slanted, striped frame). The passives are still to come in the remake.
"""
import os

ICONS = 'SpacePrototype/Content/UnleashedPrototype/GUI/Art/Iconography/Powers/'
# (id, Chorus's PowerName, name, description, its powers-screen icon, stats)
RITES = [
    ('chorus_rite_hunt', 'Blink', 'Rite of the Hunt',
     "Within the blink of an eye, leap onto the tail of the hostile ship in your sights (your lock first), facing the way it "
     "flies. Pays 2 of your 3 pips of Void energy, which grow back one every 4.5 s on a tonne of Void Crystals from the "
     "hold. Not at capital ships. (Chorus)",
     'T_Powers_Power2_Icn', {'cabinSize': 0, 'device': 23, 'deviceVoidCost': 2, 'deviceCooldownMs': 500}),
    ('chorus_rite_storm', 'Pulse', 'Rite of the Storm',
     "A bolt that disrupts the hostile ship in your sights (your lock first): its shield takes the blow, and for 4 s it can "
     "neither flee nor fire back. Pays 2 of your 3 pips of Void energy. (Chorus)",
     'T_Powers_Power4_Icn', {'cabinSize': 0, 'device': 24, 'deviceVoidCost': 2, 'deviceCooldownMs': 500, 'damage': 150,
                             'deviceDamagePercent': 50, 'deviceDurationMs': 4000}),
    ('chorus_rite_star', 'Drill', 'Rite of the Star',
     "Become a star for up to 3 s: unseen and unharmed, you spear on at three times your top speed, and every hostile ship "
     "close ahead of you burns. Press again to end it early. Pays all 3 pips of Void energy. (Chorus)",
     'T_Powers_Power5_Icn', {'cabinSize': 0, 'device': 25, 'deviceVoidCost': 3, 'deviceCooldownMs': 500, 'damage': 375,
                             'deviceDurationMs': 3000}),
    ('chorus_rite_control', 'Telekinesis', 'Rite of Control',
     "Seize the hostile ship in your sights (your lock first) and hold it beside you, helpless; press again to hurl it into "
     "another ship or anything solid, which it does not survive. Pays all 3 pips of Void energy. (Chorus)",
     'T_Powers_Power3_Icn', {'cabinSize': 0, 'device': 26, 'deviceVoidCost': 3, 'deviceCooldownMs': 500, 'damage': 250,
                             'deviceDurationMs': 8000}),
    ('chorus_rite_senses', 'SeventhSense', 'Rite of the Senses',
     "Sense what others cannot see: a wave runs out kilometres around you, uncovering cloaked ships and hidden containers, "
     "and for 20 s you see as the best scanners do, the richest asteroids marked and the cargo of the ships you lock read "
     "out. Hold it a second to sense the whole orbit. Pays 1 pip of Void energy. (Chorus)",
     'T_Powers_Power1_Icn', {'cabinSize': 0, 'device': 27, 'deviceVoidCost': 1, 'deviceCooldownMs': 500,
                             'deviceDurationMs': 20000}),
    # the passive (Chorus's BP_PassivePower_ElementalShield: BonusEnergy 2, "Prevents all elemental damage"); its icon the
    # rewards' shield upgrade (the passives have no powers-screen icon)
    ('chorus_elemental_shield', 'ElementalShield', 'Elemental Shield',
     "A ward of the Void about the hull: two more pips of Void energy for your Rites, and no harm from heat, frost or "
     "corrosion. Works while mounted. (Chorus)",
     '../Rewards/T_Reward_ShieldUpgrade_Icn', {'cabinSize': 0, 'device': 28, 'deviceVoidPips': 2, 'deviceElementalProof': 1}),
]
# the Rites' upgrades (Chorus's UpgradeDescriptionA / B; the names are the remake's) as items of their own: A, B and both
UPGRADES = {
    'chorus_rite_hunt': ('Overcharge', 'Fury', "After leaping, a bonus pip of Void energy for 10 s.",
                         "After leaping, all weapons and Rites deal 50 % more damage for 5 s."),
    'chorus_rite_storm': ('Chain', 'Absorption', "The bolt jumps on to two more ships within 500 m.",
                          "A quarter of the damage dealt goes onto your own shield."),
    'chorus_rite_star': ('Constellation', 'Renewal', "Four more burning stars circle you.",
                         "Every ship destroyed repairs a quarter of your hull."),
}

POWERS = 'SpacePrototype/Content/UnleashedPrototype/Player/Powers/'
BLINK_FX, PULSE_FX, DRILL_FX, TELEK_FX = POWERS + 'Blink/Art/', POWERS + 'Pulse/', POWERS + 'Drill/Art/', POWERS + 'Telekinesis/'
SFX = 'Sfx/Player/Active_Powers/'
SENSE_FX, SENSE_SFX = 'SpacePrototype/Content/UnleashedPrototype/Effects/7thSense/', 'Ui/Ingame/7th Sense/'
BLINK_SFX, PULSE_SFX, DRILL_SFX, TELEK_SFX = SFX + 'Blink_Chase/', SFX + 'Pulse/', SFX + 'Drill/', SFX + 'Telekinesis/'
# each Rite's looks: part -> (its particle systems, its FMOD event); 'shot' the start's sound (the fx's own). An event may be
# (event, the waves to take: a pattern, the waves to leave out: a pattern): the Drill's loop is its Loop wave alone (the
# voices over it are one-shots), its start without upgrade B's layer.
LOOKS = {
    'chorus_rite_hunt': {'shot': BLINK_SFX + 'Active_Power_Blink_Start',
                         'vanish': ([BLINK_FX + 'P_Blink_DisappearSparks'], None),
                         'appear': ([BLINK_FX + 'P_Blink_Appear'], BLINK_SFX + 'Active_Power_Blink_Appear')},
    'chorus_rite_storm': {'shot': PULSE_SFX + 'Pulse_Muzzle',
                          'start': ([PULSE_FX + 'P_Pulse_Activation'], None),
                          'hit': ([PULSE_FX + 'P_Pulse_DeBuff'], PULSE_SFX + 'Pulse_Impact')},
    'chorus_rite_star': {'shot': (DRILL_SFX + 'Bp_ActivePower_Drill_Start', None, 'Upgrades'),
                         'start': ([DRILL_FX + 'P_Drill_Init_Flash'], None),
                         'loop': ([DRILL_FX + 'P_Drill_power_MOD_loop'], (DRILL_SFX + 'Bp_ActivePower_Drill_Duration', 'Loop', None)),
                         'end': ([DRILL_FX + 'P_Drill_power_end'], DRILL_SFX + 'Bp_ActivePower_Drill_Re-Appear'),
                         'hit': ([DRILL_FX + 'P_Drill_Hit'], DRILL_SFX + 'Bp_ActivePower_Drill_Hit')},
    # (the remake's Control: 'start' at the grab, 'hit' on the held ship, 'vanish' on it as it is thrown, 'end' where it hits)
    'chorus_rite_control': {'shot': TELEK_SFX + 'Bp_ActivePower_Telekinesis_Grab',
                            'start': ([TELEK_FX + 'P_Telek_Grab_Success'], None),
                            'hit': ([TELEK_FX + 'P_Telek_Debuff_Start', TELEK_FX + 'P_Telek_Debuff_Active'], None),
                            'vanish': ([TELEK_FX + 'P_Telek_Toss_Start'], TELEK_SFX + 'Bp_ActivePower_Telekinesis_Throw'),
                            'end': ([TELEK_FX + 'P_Telek_Toss_Hit'], None)},
    # (the remake's Senses: 'start' its sphere, 'hit' as its wave uncovers a cloaked ship)
    'chorus_rite_senses': {'shot': SENSE_SFX + '7th_Sense_Scan_Activate_Short',
                           'start': ([SENSE_FX + 'P_Sphere_Expansion'], None),
                           'hit': ([], SENSE_SFX + '7th_Sense_Ping_Hit_Short_Strong_Default')},
}
LOOP_S = {'chorus_rite_star': 3.0}   # (the loop's emitters over the Star's 3 s)
FURY_S = 5.0                         # (the fury's emitters over BP_Player_Buff_Blink_UpgradeB's 5 s)
# The upgraded Rites' own looks (their BP_ActivePower_*_Upgrade* blueprints' particle systems and FMOD events) over the
# base Rite's, by (Rite, 'a' | 'b' | 'ab'); the remake's upgrade parts: 'fury' on the ship while the Hunt's B lasts (the
# Blink B muzzle and its Damage_Buff loop), 'absorb' as the Storm's B fills the shield (P_Pulse_UpgrB_ShieldAbsorb, its
# Shield_Stolen event), 'heal' as the Star's B repairs (the Drill B's Heal_Add event; no particles of its own).
_FURY = ([BLINK_FX + 'P_Muzzle_Blink_upgrade_B'], BLINK_SFX + 'Active_Power_Blink_Upgrade_B_Damage_Buff')
_ABSORB = ([PULSE_FX + 'P_Pulse_UpgrB_ShieldAbsorb'], PULSE_SFX + 'Pulse_Muzzle_Upgrade_B_Shield_Stolen')
_HEAL = ([], DRILL_SFX + 'Bp_ActivePower_Drill_Upgrade_B 2_Heal_Add')
_DRILL_END_A = [DRILL_FX + 'P_Drill_power_end', DRILL_FX + 'P_SideDrill_power_end']
UPGRADE_LOOKS = {
    ('chorus_rite_hunt', 'a'): {'shot': BLINK_SFX + 'Active_Power_Blink_Start_Upgrade_A',
                                'appear': ([BLINK_FX + 'P_Blink_Appear_UpgradeA'], BLINK_SFX + 'Active_Power_Blink_Appear_Upgrade_A')},
    ('chorus_rite_hunt', 'b'): {'shot': BLINK_SFX + 'Active_Power_Blink_Start_Upgrade_B',
                                'appear': ([BLINK_FX + 'P_Blink_Appear'], BLINK_SFX + 'Active_Power_Blink_Appear_Upgrade_B'),
                                'fury': _FURY},
    ('chorus_rite_hunt', 'ab'): {'shot': BLINK_SFX + 'Active_Power_Blink_Start_Upgrade_AB',
                                 'appear': ([BLINK_FX + 'P_Blink_Appear_UpgradeA'], BLINK_SFX + 'Active_Power_Blink_Appear_Upgrade_AB'),
                                 'fury': _FURY},
    ('chorus_rite_storm', 'a'): {'shot': PULSE_SFX + 'Pulse_Muzzle_Upgrade_A'},
    ('chorus_rite_storm', 'b'): {'shot': PULSE_SFX + 'Pulse_Muzzle_Upgrade_B', 'absorb': _ABSORB},
    ('chorus_rite_storm', 'ab'): {'shot': PULSE_SFX + 'Pulse_Muzzle_Upgrade_AB', 'absorb': _ABSORB},
    ('chorus_rite_star', 'a'): {'shot': DRILL_SFX + 'Bp_ActivePower_Drill_Start_Upgrade_A',
                                'loop': ([DRILL_FX + 'P_Drill_power_Upgrade_A'], (DRILL_SFX + 'Bp_ActivePower_Drill_Duration_Upgrade_A', 'Loop', None)),
                                'end': (_DRILL_END_A, DRILL_SFX + 'Bp_ActivePower_Drill_Re-Appear_Upgrade_A')},
    ('chorus_rite_star', 'b'): {'shot': DRILL_SFX + 'Bp_ActivePower_Drill_Start_Upgrade_B',
                                'loop': ([DRILL_FX + 'P_Drill_power_Upgrade_B'], (DRILL_SFX + 'Bp_ActivePower_Drill_Duration_Upgrade_B', 'Loop', None)),
                                'end': ([DRILL_FX + 'P_Drill_power_end'], DRILL_SFX + 'Bp_ActivePower_Drill_Re-Appear_Upgrade_B'),
                                'hit': ([DRILL_FX + 'P_Drill_Hit_UpgradeB'], DRILL_SFX + 'Bp_ActivePower_Drill_Hit'), 'heal': _HEAL},
    ('chorus_rite_star', 'ab'): {'shot': DRILL_SFX + 'Bp_ActivePower_Drill_Start_Upgrade_AB',
                                 'loop': ([DRILL_FX + 'P_Drill_power_Upgrade_B'], (DRILL_SFX + 'Bp_ActivePower_Drill_Duration_Upgrade_AB', 'Loop', None)),
                                 'end': (_DRILL_END_A, DRILL_SFX + 'Bp_ActivePower_Drill_Re-Appear_Upgrade_AB'),
                                 'hit': ([DRILL_FX + 'P_Drill_Hit_UpgradeB'], DRILL_SFX + 'Bp_ActivePower_Drill_Hit'), 'heal': _HEAL},
}
# the exporter's FMOD pattern for these
EVENTS = r'Sfx/Player/Active_Powers/(Blink_Chase|Pulse|Drill|Telekinesis)/|Ui/Ingame/7th Sense/'
HIT_LOOP_S = 4.0   # (the hit's looping emitters over BP_Buff_Pulse's 4 s, the held ship's for as long)
# a material's master -> how its image is made: ('glow') a soft disc, ('spark') the explosions' streak, ('tex', parameter(s),
# 'add' | 'alpha', the alpha-blended tint, the sheet its graph plays itself: a random frame a particle)
MATERIALS = {
    'M_Pulse_Glow_NoDepthTest': ('glow',),
    'M_Pulse_Glow': ('glow',),
    'M_Spark_01': ('spark',),
    'M_Pulse_Flare': ('tex', 'baseTex', 'add'),
    'M_Pulse_LensFlare': ('tex', 'Lensflare Texture', 'add'),
    'M_Pulse_Lines_Tex': ('tex', 'ref:T_ky_flare07_4x4', 'add'),
    'M_SmokeRisingSimple': ('tex', 'ref:T_Smoke2a_2K_Emissive', 'add'),
    'M_Pulse_BlackInk': ('tex', 'ref:T_Smoke02_01', 'alpha', [0.02, 0.02, 0.03], [8, 8]),   # (its own flipbook: 8 x 8)
    # the Drill's star: its wisps of energy plasma (an instance's own T_Smoke_01, else T_Smoke_02) and its shock ring
    'M_WispySmoke': ('tex', ('T_Smoke_01', 'T_Smoke_02'), 'add'),
    'M_UV_Accelation': ('tex', 'main', 'add'),
}

EXPORTS = [os.path.normpath(ICONS + r[4]).replace(os.sep, '/') for r in RITES]


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


def _glow(mod):
    """fx/rites/glow.png: a soft round glow (M_Pulse_Glow_NoDepthTest draws its sprite's radial falloff, no texture)."""
    import numpy as np
    from PIL import Image
    rel = 'fx/rites/glow.png'
    path = os.path.join(mod, rel)
    if not os.path.exists(path):
        y, x = np.mgrid[-1:1:128j, -1:1:128j]
        v = np.clip(1.0 - np.sqrt(x * x + y * y), 0, 1) ** 2.2
        a = (v * 255).astype(np.uint8)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(np.stack([a, a, a], -1), 'RGB').save(path, optimize=True)
    return rel


def _bake(export, mod, resolver, tex_path, blend):
    """A particle texture into the mod (at most 512): added = white on black (its brightest channel x its alpha), alpha =
    white with that as its alpha. None when it isn't exported."""
    import numpy as np
    from PIL import Image
    resolver.fetch_textures([tex_path], export)
    src = os.path.join(export, tex_path + '.png')
    if not os.path.exists(src): return None
    name = tex_path.rsplit('/', 1)[-1]
    rel = f'fx/rites/{name}_{blend}.png'
    dst = os.path.join(mod, rel)
    if not os.path.exists(dst):
        im = Image.open(src).convert('RGBA')
        if max(im.size) > 512: im = im.resize((min(512, im.width), min(512, im.height)), Image.LANCZOS)
        a = np.asarray(im).astype(np.float32) / 255.0
        alpha = a[..., 3] if a[..., 3].min() < 0.99 else 1.0
        v = np.clip(a[..., :3].max(-1) * alpha, 0, 1)
        g = (v * 255).astype(np.uint8)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if blend == 'alpha':
            w = np.full_like(g, 255)
            Image.fromarray(np.stack([w, w, w, g], -1), 'RGBA').save(dst, optimize=True)
        else:
            Image.fromarray(np.stack([g, g, g], -1), 'RGB').save(dst, optimize=True)
    return rel


def _picker(export, mod, resolver):
    """explosions._emitters' 'pick': an emitter's image by its material's master (MATERIALS), None = left out."""
    from . import explosions
    def pick(mat_name, mat_path):
        p = resolver.get(mat_path) if mat_path else None
        master = (p.chain or [None])[-1] if p else None
        how = MATERIALS.get(master)
        if not how: return None
        if how[0] == 'glow': return _glow(mod), None, None
        if how[0] == 'spark': return explosions._spark(mod), None, None
        tex = p.texture(*(how[1] if isinstance(how[1], tuple) else (how[1],)))
        path = p.texture_paths.get(tex) if tex else None
        image = _bake(export, mod, resolver, path, how[2]) if path else None
        if not image: return None
        if len(how) > 4: pick.sheets[image] = how[4]
        return image, ('alpha' if how[2] == 'alpha' else None), (how[3] if len(how) > 3 else None)
    pick.sheets = {}   # image -> the sheet its material plays itself
    return pick


def _systems(work, resolver, paths):
    """The Cascade systems' JSON (dumped once into <work>/bp_rites)."""
    import json, re
    folder = os.path.join(work, 'bp_rites'); os.makedirs(folder, exist_ok=True)
    todo = [p for p in paths if not os.path.exists(os.path.join(folder, p.rsplit('/', 1)[1] + '.json'))]
    if todo and resolver is not None:
        resolver.run('jsonall', '/(' + '|'.join(re.escape(p.rsplit('/', 1)[1]) for p in todo) + r')\.uasset$', folder, capture=True)
    out = []
    for p in paths:
        f = os.path.join(folder, p.rsplit('/', 1)[1] + '.json')
        if os.path.exists(f): out.append(json.load(open(f, encoding='utf-8')))
    return out


MAX_VARIANTS = 4


def _variants(waves):
    """An event's waves as its versions to write: [[files to mix], ...]. Waves of one name numbered are one layer's
    variations (an FMOD multi instrument), each other name a layer played with it; version i mixes each layer's i-th
    variation (round the shorter ones), at most MAX_VARIANTS."""
    import re
    groups = {}
    for w in sorted(waves):
        stem = re.sub(r'\s*-\s*trimmed$', '', os.path.splitext(os.path.basename(w))[0], flags=re.I)
        groups.setdefault(re.sub(r'[_ -]*\d+$', '', stem), []).append(w)
    if not groups: return []
    n = min(MAX_VARIANTS, max(len(g) for g in groups.values()))
    return [[g[i % len(g)] for g in groups.values()] for i in range(n)]


def _as_alpha(mod, rel):
    """An added image (white on black) as an alpha mask of white: dark smoke drawn over what is behind."""
    import numpy as np
    from PIL import Image
    alpha_rel = rel.replace('_add.png', '_alpha.png') if rel.endswith('_add.png') else rel[:-4] + '_alpha.png'
    dst = os.path.join(mod, alpha_rel)
    if not os.path.exists(dst):
        g = np.asarray(Image.open(os.path.join(mod, rel)).convert('L'))
        w = np.full_like(g, 255)
        Image.fromarray(np.stack([w, w, w, g], -1), 'RGBA').save(dst, optimize=True)
    return alpha_rel


def _dark_smoke(mod, ems):
    """Translucent smoke (M_SmokeRisingSimple) the particle colour leaves black reads as dark smoke in Chorus, nothing when
    added: drawn alpha-blended in a near black."""
    for e in ems:
        if e.get('blend') or not e.get('image') or max(e.get('color') or [1]) > 0.05: continue
        e['image'] = _as_alpha(mod, e['image'])
        e['blend'] = 'alpha'
        e['color'] = [0.02, 0.02, 0.03]
        e.pop('colorOverLife', None)
    return ems


def _sound(fmod_dir, mod, event, rid):
    """An FMOD event's waves as Ogg files in <mod>/audio/: a list of mod paths (one at random), [] without ffmpeg or waves.
    'event' a path, or (path, the waves to take, the waves to leave out) as patterns."""
    import json, re, subprocess
    from . import sounds
    take = leave = None
    if isinstance(event, tuple): event, take, leave = event
    if not fmod_dir or not sounds.ffmpeg() or not os.path.exists(os.path.join(fmod_dir, 'events.json')): return []
    events = json.load(open(os.path.join(fmod_dir, 'events.json'), encoding='utf-8'))
    waves = [w for w in events.get('event:/' + event, {}).get('waves', []) if os.path.exists(os.path.join(fmod_dir, w))
             and (not take or re.search(take, os.path.basename(w))) and not (leave and re.search(leave, os.path.basename(w)))]
    out = []
    for i, layers in enumerate(_variants(waves)):
        rel = f"audio/{rid}_{re.sub(r'[^a-z0-9]+', '_', event.rsplit('/', 1)[-1].lower())}_{i + 1}.ogg"
        dst = os.path.join(mod, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if len(layers) == 1: sounds.write(os.path.join(fmod_dir, layers[0]), dst)
        else:
            args = [sounds.ffmpeg(), '-v', 'error', '-y']
            for w in layers: args += ['-i', os.path.join(fmod_dir, w)]
            args += ['-filter_complex', f'amix=inputs={len(layers)}:normalize=0', '-ac', '2', '-c:a', 'libvorbis', '-q:a', '5', dst]
            subprocess.run(args, check=True)
        out.append(rel)
    return out


def looks(export, mod, resolver, work, fmod_dir, rid, tag=None):
    """A Rite's items.json "fx": its start sound ("shot") and its looks file ("rite": fx/rite_<id>.json); with 'tag' ('a', 'b',
    'ab') an upgraded one's (UPGRADE_LOOKS over the base Rite's, fx/rite_<id>_<tag>.json). {} without either."""
    import json
    from . import explosions
    if rid not in LOOKS: return {}
    spec = dict(LOOKS[rid])
    if tag: spec.update(UPGRADE_LOOKS.get((rid, tag), {}))
    key = f'{rid}_{tag}' if tag else rid
    fx, rite = {}, {}
    shot = _sound(fmod_dir, mod, spec['shot'], key) if spec.get('shot') else []
    if shot: fx['shot'] = shot
    pick = _picker(export, mod, resolver) if resolver is not None else None
    for part in ('start', 'vanish', 'appear', 'hit', 'loop', 'end', 'fury', 'absorb', 'heal'):
        if part not in spec: continue
        systems, event = spec[part]
        ems = []
        if pick:
            for d in _systems(work, resolver, systems):
                loop_for = HIT_LOOP_S if part == 'hit' else LOOP_S.get(rid) if part == 'loop' else FURY_S if part == 'fury' else None
                ems += explosions._emitters(export, mod, resolver, d, pick=pick, loop_for=loop_for)
        for e in ems:
            sheet = pick.sheets.get(e.get('image')) if pick else None
            if sheet and 'sheet' not in e: e['sheet'] = sheet; e['randomFrame'] = True
        if ems: rite[part] = {'emitters': _dark_smoke(mod, ems)}
        snd = _sound(fmod_dir, mod, event, key) if event else []
        if snd: rite[part + 'Sound'] = snd
    if rite:
        rel = f'fx/rite_{key}.json'
        os.makedirs(os.path.join(mod, 'fx'), exist_ok=True)
        json.dump(rite, open(os.path.join(mod, rel), 'w', encoding='utf-8'), indent=1)
        fx['rite'] = rel
        print(f"  rites: {key}: " + ', '.join(f"{k} {len(v['emitters'])}" for k, v in rite.items() if isinstance(v, dict)))
    return fx


def items(export, out, resolver=None, work=None, fmod_dir=None):
    """items.json entries for the Rites; their icons into <out>/icons/ (none without the export or PIL: the cabin's), their
    looks with a resolver (the particles) and the FMOD export (the sounds)."""
    result = []
    for rid, _, name, desc, icon, stats in RITES:
        it = {'id': rid, 'base': 91, 'name': name, 'description': desc, 'techLevel': 9, 'occurrence': 2,
              'price': [250000, 262000], 'stats': dict(stats)}
        src = os.path.join(export, os.path.normpath(ICONS + icon) + '.png')
        if os.path.exists(src):
            try:
                os.makedirs(os.path.join(out, 'icons'), exist_ok=True)
                _icon(src, os.path.join(out, 'icons', rid + '.png'))
                it['icon'] = f'icons/{rid}.png'
            except ImportError:
                pass
        fx = looks(export, out, resolver, work, fmod_dir, rid) if work else {}
        if fx: it['fx'] = fx
        result.append(it)
        result += upgraded(it, export, out, resolver, work, fmod_dir)
    return result


def upgraded(base, export=None, out=None, resolver=None, work=None, fmod_dir=None):
    """The Rite 'base''s upgraded items (UPGRADES): A, B and both (the remake's deviceUpgrade 1 / 2 / 3), its icon and looks,
    later in the game and dearer; none for a Rite without upgrades."""
    up = UPGRADES.get(base['id'])
    if not up: return []
    name_a, name_b, text_a, text_b = up
    result_items = []
    for mask, tag, name, text, scale in ((1, 'a', name_a, text_a, 1.5), (2, 'b', name_b, text_b, 1.5),
                                         (3, 'ab', f'{name_a} and {name_b}', f'{text_a} {text_b}', 2.2)):
        it = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in base.items()}
        it['id'] = f"{base['id']}_{tag}"
        it['name'] = f"{base['name']}: {name}"
        it['description'] = base['description'].replace(' (Chorus)', '') + ' ' + text + ' (Chorus)'
        it['techLevel'] = 10
        it['occurrence'] = 1
        it['price'] = [round(p * scale) for p in base['price']]
        it['stats']['deviceUpgrade'] = mask
        if work and (base['id'], tag) in UPGRADE_LOOKS:   # (its own looks; else the base Rite's, copied above)
            fx = looks(export, out, resolver, work, fmod_dir, base['id'], tag)
            if fx: it['fx'] = fx
        result_items.append(it)
    return result_items
