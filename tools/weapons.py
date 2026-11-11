"""The chorus_ships mod's weapons: Chorus's fifteen player weapons (three kinds, T1 and the A / B branches of T2 and T3) as
items for the remake (items.json), each on the original item of its kind it plays like, with Chorus's own names,
descriptions, sounds and colours.

Read from the player's copy at build time (nothing of Chorus is in this file):
  names and descriptions   BP_PlayerEquipmentMasterData's WeaponsMasterData (ItemName -> ItemDisplayName / ItemDescription
                           and the perk lines), exported by import.py
  shot sounds              each weapon's muzzle event (the exporter's fmod output)
The numbers below are from Chorus's weapon blueprints (Player/Weapons/Primary/<kind>/<tier>, read 2026-11-11; T2 / T3 change
only what they override). Damage per second keeps Chorus's ratios on the original's scale: x1/3 (Chorus's T1 gatling, 133
a second, is the Mass Driver MD 10's 44), within the game's fire rates (90 ms the fastest). Chorus's perks become what the
remake has: the ricochet and the kill explosions an echo blast, the slug bursts and charged salvos a salvo, the paralysis EMP.
In Chorus all fifteen are primaries; Galaxy on Fire 2 has no missile primaries, so the launchers fire secondary missiles.
"""
import json, os, re
import numpy as np
from tools import sounds

SHOT_FILE_LEVEL = 0.371
WEAPONS = 'Sfx/Player/Player Weapons/'
G, L, M = 'Gatlings/', 'Lasers/', 'Missile_Launchers/'
ORANGE, RED, VIOLET, CYAN = [1.0, 0.18, 0.1], [1.0, 0.1, 0.08], [0.7, 0.3, 1.0], [0.3, 0.8, 1.0]

# (id, Chorus ItemName, base item, tech level, price, stats, fx colour, muzzle event, its shot waves, loops)
TABLE = [
    # Gatlings: T1 Talon 4 every 0.03 s (133 / s); A: Reaping Storm (2.6 every 0.01 s, 4 deg spread, 260 / s; T3 3.6 and a
    # ricochet: 10x within 200 m); B: Slug Shots (4 shots of 52 per 0.9 s, 231 / s; T3 72, the last x2 on armour)
    ('chorus_gatling_t1', 'Gatling_T1', 27, 7, [92000, 98000], {'damage': 4, 'loadingTimeMs': 90, 'range': 1400, 'projectileSpeed': 30},
     ORANGE, G + 'T1_GatlingHitscan/T1_GatlingHitscan_Muzzle_Loop', r'^Sfx_GatlingT1_Loop_01 - Trimmed$', True),
    ('chorus_gatling_t2a', 'Gatling_T2_01', 27, 8, [140000, 148000], {'damage': 8, 'loadingTimeMs': 90, 'range': 1100, 'projectileSpeed': 30},
     ORANGE, G + 'T2_Gatling_T2_A/T2_Gatling_T2_A_Muzzle_Loop_with_Muzzle', r'^Weapon_GatlingT2_A_Muzzle[_ -]*\d+$', False),
    ('chorus_gatling_t3a', 'Gatling_T3_01', 230, 9, [300000, 315000],
     {'damage': 11, 'loadingTimeMs': 90, 'range': 1100, 'projectileSpeed': 30, 'echoDelayMs': 100, 'echoPercent': 30, 'echoRadius': 4000},
     ORANGE, G + 'T3_Gatling_T3 A/T3_Gatling_T3_A_Muzzle_Loop_with_Muzzle', r'^Weapon_GatlingT3_A_Muzzle[_ -]*\d+$', False),
    ('chorus_gatling_t2b', 'Gatling_T2_02', 27, 8, [140000, 148000],
     {'damage': 17, 'loadingTimeMs': 112, 'range': 1400, 'projectileSpeed': 30, 'salvoShots': 1, 'salvoCount': 4, 'salvoGapMs': 112, 'reloadMs': 450},
     ORANGE, G + 'T2_Gatling_T2_B/T2_Gatling_T2_B_Muzzle', r'^Weapon_GatlingT2_B_Muzzle_v[_ -]*\d+$', False),
    ('chorus_gatling_t3b', 'Gatling_T3_02', 230, 9, [300000, 315000],
     {'damage': 24, 'loadingTimeMs': 112, 'range': 1400, 'projectileSpeed': 30, 'salvoShots': 1, 'salvoCount': 4, 'salvoGapMs': 112, 'reloadMs': 450},
     ORANGE, G + 'T3_Gatling_T3_B/T3_Gatling_T3_B_Muzzle', r'^Weapon_GatlingT3_B_Muzzle[_ -]*\d+$', False),
    # Lasers: T1 Glow 25 a charged shot every 0.3 s (83 / s); A: Discharge Limiter (69 every 0.15 s from 5 charges; T3 94 and
    # paralysis); B: Explosive Overload (55, a 220 kill explosion within 150 m; T3 75 and 300)
    ('chorus_laser_t1', 'Laser_T1', 8, 7, [80000, 84000], {'damage': 25, 'loadingTimeMs': 900, 'range': 2600, 'projectileSpeed': 28},
     None, L + 'T1_LaserRifleHitscan/T1_LaserRifleHitscan_Muzzle', r'^Sfx_Player_Weapon_Laser_T1_Heavy_Reduced_6ch-\d+$', False),
    ('chorus_laser_t2a', 'Laser_T2_01', 8, 8, [130000, 136000], {'damage': 23, 'loadingTimeMs': 300, 'range': 2600, 'projectileSpeed': 28},
     CYAN, L + 'T2_Laser_T2_A/T2_Laser_T2_A_Muzzle', r'^Weapon_LaserT2_A_Muzzle[_ -]*\d+$', False),
    ('chorus_laser_t3a', 'Laser_T3_01', 11, 9, [290000, 305000], {'damage': 31, 'empDamage': 15, 'loadingTimeMs': 300, 'range': 2600, 'projectileSpeed': 28},
     CYAN, L + 'T3_Laser_T3_A/T3_Laser_T3_A_Muzzle', r'^Weapon_LaserT3_A_Muzzle[_ -]*\d+$', False),
    ('chorus_laser_t2b', 'Laser_T2_02', 8, 8, [130000, 136000],
     {'damage': 55, 'loadingTimeMs': 900, 'range': 2600, 'projectileSpeed': 28, 'echoDelayMs': 60, 'echoPercent': 60, 'echoRadius': 3000},
     RED, L + 'T2_Laser_T2_B/T2_Laser_T2_B_Muzzle', r'^Weapon_Laser_T2_B_Muzzle[_ -]*\d+$', False),
    ('chorus_laser_t3b', 'Laser_T3_02', 11, 9, [290000, 305000],
     {'damage': 75, 'loadingTimeMs': 900, 'range': 2600, 'projectileSpeed': 28, 'echoDelayMs': 60, 'echoPercent': 80, 'echoRadius': 3000},
     VIOLET, L + 'T3_Laser_T3_B/T3_Laser_T3_B_Muzzle', r'^Weapon_Laser_T3_B_Muzzle[_ -]*\d+$', False),
    # Missile launchers: T1 Javelin homing at 1080 m/s, 28 area + shrapnel every 0.225 s; A: Heavy Spears (one powerful
    # rocket a second, 8 rounds; T3 a contaminated zone); B: cluster bolas (T3 seeking the most damaged target)
    ('chorus_missiles_t1', 'MissileLauncher_T1', 37, 7, [300, 320],
     {'damage': 110, 'empDamage': 0, 'loadingTimeMs': 3000, 'range': 8000, 'projectileSpeed': 24, 'salvoShots': 2},
     RED, M + 'T1_MissileLauncher/T1_MissileLauncher_Muzzle', r'^Weapon_Artillery_Rocket_\d+$', False),
    ('chorus_missiles_t2a', 'MissileLauncher_T2_01', 37, 8, [700, 740],
     {'damage': 300, 'empDamage': 0, 'loadingTimeMs': 4000, 'range': 8000, 'projectileSpeed': 20},
     RED, M + 'T2_MissileLauncher_T2_A/T2_MissileLauncher_T2_A_Muzzle', r'^Weapon_Missile_T2_A_Muzzle[_ -]*\d+$', False),
    ('chorus_missiles_t3a', 'MissileLauncher_T3_01', 40, 9, [1200, 1260],
     {'damage': 380, 'empDamage': 0, 'loadingTimeMs': 4000, 'range': 9000, 'projectileSpeed': 20, 'echoDelayMs': 1000, 'echoPercent': 40, 'echoRadius': 4000},
     [0.5, 1.0, 0.2], M + 'T3_MissileLauncher_T3_A/T3_MissileLauncher_T3_A_Muzzle', r'^Weapon_Missile_T3_A_Muzzle[_ -]*\d+$', False),
    ('chorus_missiles_t2b', 'MissileLauncher_T2_02', 214, 8, [520, 550], {'damage': 70, 'range': 8000, 'projectileSpeed': 10},
     RED, M + 'T2_MissileLauncher_T2_B_Fragmentation/T2_MissileLauncher_T2_B_Muzzle', r'^Weapon_Missile_T2_B_Muzzle[_ -]*\d+$', False),
    ('chorus_missiles_t3b', 'MissileLauncher_T3_02', 216, 9, [1300, 1380], {'damage': 95, 'range': 10000, 'projectileSpeed': 11},
     RED, M + 'T3_MissileLauncher_T3_B/T3_MissileLauncher_T3_B_Muzzle', r'^Weapon_Missile_T3_B_Muzzle[_ -]*\d+$', False),
]
# The exporter's pattern for every event above.
EVENTS = r'Sfx/Player/Player Weapons/(Gatlings|Lasers|Missile_Launchers)/T[123][^/]*/[^/]*Muzzle'
OCCURRENCE = {7: 20, 8: 12, 9: 6}


def _text(t):
    if isinstance(t, dict): return t.get('LocalizedString') or t.get('SourceString') or t.get('CultureInvariantString') or ''
    return t or ''


def names(master_json):
    """Chorus's ItemName -> (display name, description with its perks), from the exported master data ({} without it)."""
    if not master_json or not os.path.exists(master_json): return {}
    out = {}
    for export in json.load(open(master_json, encoding='utf-8')):
        for w in (export.get('Properties') or {}).get('WeaponsMasterData', []):
            name = ' '.join(_text(w.get('ItemDisplayName')).split()).title()
            perks = [_text(w.get(k)) for k in ('PerkDescription0', 'PerkDescription1', 'PerkDescription')]
            perks = [p[0] + p[1:].lower() if p.isupper() else p for p in perks if p]
            desc = ' '.join([_text(w.get('ItemDescription'))] + [p.split(' - ', 1)[-1] if ' - ' in p else p for p in perks]).strip()
            out[w.get('ItemName')] = (name, desc)
    return out


def build(fmod_dir, mod, master_json=None):
    """items.json entries for the fifteen weapons; their sound files go to <mod>/audio/ (without ffmpeg or the export: the
    base items' sounds; without the master data: plain names)."""
    events = {}
    path = os.path.join(fmod_dir, 'events.json') if fmod_dir else None
    if path and os.path.exists(path): events = json.load(open(path, encoding='utf-8'))
    text = names(master_json)
    out = []
    for wid, chorus, base, tl, price, stats, colour, event, pattern, loop in TABLE:
        name, desc = text.get(chorus, (None, ''))
        kind = 'Gatling' if 'gatling' in wid else 'Laser' if 'laser' in wid else 'Missiles'
        item = {'id': wid, 'base': base, 'name': name or f'Chorus {kind} {wid.rsplit("_", 1)[-1].upper()}',
                'description': (desc + ' (Chorus)').strip() if desc else 'A weapon from Chorus.',
                'techLevel': tl, 'occurrence': OCCURRENCE[tl], 'price': price, 'stats': dict(stats)}
        fx = {}
        if colour: fx['projectile'] = {'color': colour, 'glow': 3 if 'missiles' not in wid else 2}
        waves = sorted(x for x in events.get('event:/' + WEAPONS + event, {}).get('waves', [])
                       if re.match(pattern, os.path.splitext(os.path.basename(x))[0]))
        if waves and sounds.ffmpeg():
            levels = [sounds.loudness(*sounds.read(os.path.join(fmod_dir, x)), loop) for x in waves]
            peak = max(float(np.abs(sounds.read(os.path.join(fmod_dir, x))[0]).max()) for x in waves) + 1e-9
            gain = min(SHOT_FILE_LEVEL / float(np.median(levels)), 0.98 / peak)
            files = []
            for x in waves:
                fname = 'audio/' + wid + '_' + re.sub(r'[^a-z0-9]+', '_', os.path.splitext(os.path.basename(x))[0].lower()).strip('_') + '.ogg'
                sounds.write(os.path.join(fmod_dir, x), os.path.join(mod, fname), gain)
                files.append(fname)
            fx['shot'] = files if len(files) > 1 else files[0]
            fx['shotLoops'] = loop
        if fx: item['fx'] = fx
        out.append(item)
    return out
