"""The chorus_ships mod's weapons: the Forsaken's three T1 weapons from Chorus as items for the remake (items.json), each on
the original item of its kind it plays like, with Chorus's own sounds and colours.

Chorus's weapon blueprints (Player/Weapons/Primary/*/T1, read 2026-11-11):
  Gatling (BP_Player_Weapon_GatlingHitscan)            4 per shot every 0.03 s (ramping up over 5 s), ~133 per second;
                                                        orange tracers (ColorChangeVariantA 500 / 87.5 / 50)
  Laser rifle (BP_Player_Weapon_LaserRifleHitscan)      25 per charged shot every 0.3 s, ~83 per second, x1.5 on shields
  Missile launcher (BP_Player_Weapon_MissileLauncher)   homing missiles at 1080 m/s (HomingAccelerationMagnitude 5000),
                                                        28 area damage and shrapnel, x2 on armour and hull, red
In Chorus all three are primaries the player switches between. Galaxy on Fire 2 has no missile primaries, so the launcher
becomes a secondary: a homing missile fired in pairs. The numbers keep Chorus's proportions on the original's scale: the
gatling is the Mass Driver MD 10's (4 every 90 ms, its auto-cannon class), the laser rifle 0.62 of that per second (Chorus's
83 / 133) in heavy shots, Chorus's own 25 every 0.9 s, on the Berger Converge IV, faster and longer-ranged (Chorus's laser
is hitscan). Weapon models on the mounts would need the ship as a ship kit (hardpoint models): not done.

Sounds come from the exporter's fmod output like the ship's (sounds.py) and are written at the level of the game's own shots
(the Nirai Impulse's wave, 0.371 loudest-60-ms: an item's shot sound has no volume field, so the level is in the file)."""
import json, os, re
import numpy as np
from tools import sounds

SHOT_FILE_LEVEL = 0.371
WEAPONS = 'Sfx/Player/Player Weapons/'

ITEMS = [
    {'id': 'chorus_gatling', 'base': 27, 'name': 'Forsaken Gatling',
     'description': "The Forsaken's twin rotary gun from Chorus: a hail of small rounds that tears through hulls.",
     'techLevel': 8, 'occurrence': 15, 'price': [118000, 124000],
     'stats': {'damage': 4, 'loadingTimeMs': 90, 'range': 1400, 'projectileSpeed': 30},
     'sound': ('Gatlings/T1_GatlingHitscan/T1_GatlingHitscan_Muzzle_Loop', r'^Sfx_GatlingT1_Loop_01 - Trimmed$', True),
     'fx': {'projectile': {'color': [1.0, 0.18, 0.1], 'glow': 3}, 'muzzle': {'color': [1.0, 0.45, 0.2]}}},
    {'id': 'chorus_laser_rifle', 'base': 8, 'name': 'Forsaken Laser Rifle',
     'description': "The Forsaken's charged laser rifle from Chorus: slow, heavy shots that cut through shields.",
     'techLevel': 8, 'occurrence': 15, 'price': [86000, 90000],
     'stats': {'damage': 25, 'loadingTimeMs': 900, 'range': 2600, 'projectileSpeed': 28},
     'sound': ('Lasers/T1_LaserRifleHitscan/T1_LaserRifleHitscan_Muzzle', r'^Sfx_Player_Weapon_Laser_T1_Heavy_Reduced_6ch-\d+$', False),
     'fx': {}},
    {'id': 'chorus_missiles', 'base': 37, 'name': 'Forsaken Missiles',
     'description': "Chorus's homing missiles, fired in pairs from the Forsaken's launcher: fast, and hard on armour.",
     'techLevel': 7, 'occurrence': 30, 'price': [300, 320],
     'stats': {'damage': 110, 'empDamage': 0, 'loadingTimeMs': 3000, 'range': 8000, 'projectileSpeed': 24, 'salvoShots': 2},
     'sound': ('Missile_Launchers/T1_MissileLauncher/T1_MissileLauncher_Muzzle', r'^Weapon_Artillery_Rocket_\d+$', False),
     'fx': {'projectile': {'color': [1.0, 0.1, 0.08], 'glow': 2}}},
]
EVENTS = r'Sfx/Player/Player Weapons/(Gatlings/T1_GatlingHitscan/|Lasers/T1_LaserRifleHitscan/|Missile_Launchers/T1_MissileLauncher/)'


def build(fmod_dir, mod):
    """items.json entries for the three weapons; their sound files go to <mod>/audio/ (without ffmpeg or the export: the
    base items' sounds)."""
    events = {}
    path = os.path.join(fmod_dir, 'events.json') if fmod_dir else None
    if path and os.path.exists(path): events = json.load(open(path, encoding='utf-8'))
    out = []
    for w in ITEMS:
        item = {k: v for k, v in w.items() if k not in ('sound', 'fx')}
        fx = dict(w['fx'])
        event, pattern, loop = w['sound']
        waves = sorted(x for x in events.get('event:/' + WEAPONS + event, {}).get('waves', [])
                       if re.match(pattern, os.path.splitext(os.path.basename(x))[0]))
        if waves and sounds.ffmpeg():
            levels = [sounds.loudness(*sounds.read(os.path.join(fmod_dir, x)), loop) for x in waves]
            peak = max(float(np.abs(sounds.read(os.path.join(fmod_dir, x))[0]).max()) for x in waves) + 1e-9
            gain = min(SHOT_FILE_LEVEL / float(np.median(levels)), 0.98 / peak)
            files = []
            for x in waves:
                name = 'audio/' + w['id'] + '_' + re.sub(r'[^a-z0-9]+', '_', os.path.splitext(os.path.basename(x))[0].lower()).strip('_') + '.ogg'
                sounds.write(os.path.join(fmod_dir, x), os.path.join(mod, name), gain)
                files.append(name)
            fx['shot'] = files if len(files) > 1 else files[0]
            fx['shotLoops'] = loop
        if fx: item['fx'] = fx
        out.append(item)
    return out
