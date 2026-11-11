"""Chorus's regions as a cluster of new systems (the remake's systems.json / stations.json, Modding/README "Systems"): Stega,
Amarok, Nimika and Tarris, past Pescal Inartu at the top of the map, one jumpgate from it into Stega and the four linked
among themselves; each with its region's sky (tools/sky.py, live and baked) and its stations' planets drawn as Chorus draws
them (tools/planets.py). The game's systems stay as they are.

Names from Chorus's own text (GameUI / Maps locres: MAP_Location_Stega / Amarok / NimikaPrime / Tarris, the map's
locations). The Enclave, Helios, Eos, Nimika's ring station and Tarris's big station (Achunal Labs) are Chorus's own
(tools/stations.py); Stega Belt and the Tarris Wormhole look like an original station (looksLike).
"""
import json, math, os, random
import numpy as np
from . import gate as chorus_gate, glb, npcs, planets, rocks, sky, stations as chorus_stations

MOD = 'chorus_ships'
GATE_FROM = 18   # Pescal Inartu (Terran, security 1): the cluster's way in
# (id, name, map position 0-100, security, visible at the start, sky key, gates within the cluster)
SYSTEMS = [
    ('stega', 'Stega', [30, 93, 86], 1, True, 'stega', [GATE_FROM, f'{MOD}:amarok', f'{MOD}:nimika']),
    ('amarok', 'Amarok', [19, 97, 77], 0, False, 'amarok', [f'{MOD}:tarris']),
    ('nimika', 'Nimika', [38, 99, 96], 1, False, 'nimika_b', [f'{MOD}:tarris']),
    ('tarris', 'Tarris', [11, 93, 92], 0, False, 'tarris_b', []),
]
# (id, system, name, tech level, planet key, looks like)
STATIONS = [
    ('the_enclave', 'stega', 'The Enclave', 5, 'stega_world', 41),
    ('stega_belt', 'stega', 'Stega Belt', 3, 'stega_giant', 40),
    ('helios', 'amarok', 'Helios', 4, 'amarok_world', 41),
    ('eos', 'amarok', 'Eos Station', 5, 'amarok_world', 40),
    ('nimika_prime', 'nimika', 'Nimika Prime', 6, 'nimika_world', 40),
    ('achunal_labs', 'tarris', 'Achunal Labs', 7, 'tarris_world', 41),
    ('tarris_wormhole', 'tarris', 'Tarris Wormhole', 4, 'tarris_giant', 40),
]
# each orbit's set dressing: (asteroid field count or 0, giant rocks): Chorus's field asteroids mined like the game's, its
# giant rocks as props (scaled to the game's orbits: a 9 km Chorus rock would be 180 000 units; these 15 000 - 45 000)
DRESSING = {'the_enclave': (0, 3), 'stega_belt': (140, 6), 'helios': (60, 4), 'eos': (0, 2), 'nimika_prime': (90, 5),
            'achunal_labs': (0, 2), 'tarris_wormhole': (80, 4)}
# wreck fields (the remake's salvage containers among hulks): Chorus's own freighters and capital ships from this mod
# (tools/npcs.py) as the hulks; Nimika Prime's the largest, its planet broken by the Rift
WRECKS = {'stega_belt': 10, 'nimika_prime': 16, 'tarris_wormhole': 8}
WRECK_HULLS = ('civ_liner', 'atlas', 'atlas_mk3', 'frigate_mk2', 'dropship')
# the destroyed moon (SM_Moon_Destroyed_*, about 6 km): its three shell pieces share one frame and go back together at one
# place, turn and scale (each sized by its own extent: a prop is placed at its origin, fitted by its largest side); the
# loose rocks round it at the same scale
MOON_AT = {'nimika_prime': (90000, 4000, -60000)}
MOON_SCALE = 10.0   # (game units per Chorus metre: 3 km here)
MOON_SHELL = ('SM_Moon_Destroyed_01', 'SM_Moon_Destroyed_02', 'SM_Moon_Destroyed_03')
GIANT_SIZE = (15000, 45000)
GIANT_RING = (70000, 160000)   # (their distance from the station: clear of it, the gate and the arrival)
# Chorus's stations' own models (tools/stations.py) and their size here in game units (the originals are 20 000 - 100 000)
MODEL_SIZE = {'the_enclave': 100000, 'helios': 70000, 'eos': 60000, 'nimika_prime': 80000, 'achunal_labs': 80000}
GATE_STATIONS = {'stega': 'the_enclave', 'amarok': 'helios', 'nimika': 'nimika_prime', 'tarris': 'achunal_labs'}


def _extent(mod, rel):
    g, b = glb.load(os.path.join(mod, rel))
    lo = np.min([acc['min'] for acc in g['accessors'] if 'min' in acc and len(acc['min']) == 3], 0)
    hi = np.max([acc['max'] for acc in g['accessors'] if 'max' in acc and len(acc['max']) == 3], 0)
    return float((hi - lo).max())


def _moon(tid, rock, mod, rnd):
    models, mats = rock.get('moon', ([], []))
    if tid not in MOON_AT or not models: return [], []
    at = list(MOON_AT[tid]); turn = [round(rnd.uniform(0, 360)) for _ in range(3)]
    props = []
    for rel in models:
        size = round(_extent(mod, rel) * MOON_SCALE)
        if any(k in rel for k in MOON_SHELL):
            props.append({'model': rel, 'at': at, 'rotation': turn, 'size': size})
        else:
            a = rnd.uniform(0, 6.283); d = rnd.uniform(45000, 80000)
            props.append({'model': rel, 'at': [round(at[0] + math.cos(a) * d), round(at[1] + rnd.uniform(-20000, 20000)), round(at[2] + math.sin(a) * d)],
                          'rotation': [round(rnd.uniform(0, 360)) for _ in range(3)], 'size': size})
    return props, mats


def _dressing(tid, rock, hulls=None, mod=None):
    """The orbit's asteroid field, giant rocks and wreck field (the same for every build: seeded by the station)."""
    count, giants = DRESSING.get(tid, (0, 0))
    rnd = random.Random(tid)
    orbit = {}
    field_models, field_mats = rock.get('field', ([], []))
    if count and field_models:
        a = rnd.uniform(0, 6.283); d = rnd.uniform(50000, 90000)
        orbit['asteroids'] = {'count': count, 'centre': [round(math.cos(a) * d), round(rnd.uniform(-8000, 8000)), round(math.sin(a) * d)],
                              'spread': 130000, 'type': 'rock', 'models': field_models, 'materials': field_mats}
    giant_models, giant_mats = rock.get('giant', ([], []))
    moon_props, moon_mats = _moon(tid, rock, mod, rnd) if mod else ([], [])
    if moon_props:
        orbit['props'] = moon_props; orbit['propMaterials'] = list(moon_mats)
    if giants and giant_models:
        props = []
        for k in range(giants):
            a = rnd.uniform(0, 6.283); d = rnd.uniform(*GIANT_RING); h = rnd.uniform(-0.25, 0.25) * d
            props.append({'model': rnd.choice(giant_models), 'at': [round(math.cos(a) * d), round(h), round(math.sin(a) * d)],
                          'rotation': [round(rnd.uniform(0, 360)), round(rnd.uniform(0, 360)), round(rnd.uniform(0, 360))],
                          'size': round(rnd.uniform(*GIANT_SIZE))})
        orbit['props'] = orbit.get('props', []) + props
        orbit['propMaterials'] = orbit.get('propMaterials', []) + giant_mats
    if WRECKS.get(tid) and hulls:
        a = rnd.uniform(0, 6.283); d = rnd.uniform(40000, 70000)
        mats, seen = [], set()
        for e in hulls:
            for m in e.get('materials', []):
                if m['material'] not in seen: seen.add(m['material']); mats.append(m)
        orbit['wrecks'] = {'count': WRECKS[tid], 'centre': [round(math.cos(a) * d), round(rnd.uniform(-5000, 5000)), round(math.sin(a) * d)],
                           'spread': 60000, 'models': [e['model'] for e in hulls], 'materials': mats, 'hulks': 6, 'size': 9000}
    return orbit


def _export(run, export, paths, quality=None):
    """Exports the pak paths not exported yet (one exporter run)."""
    todo = [p for p in paths if not os.path.exists(os.path.join(export, p + '.glb'))]
    if not todo: return
    lst = os.path.join(export, '..', 'world_list.txt')
    open(lst, 'w').write('\n'.join(todo) + '\n')
    run('export', lst, export, *([quality] if quality else []), capture=True)


def build(export, mod, resolver, run, ships=None):
    """Writes <mod>/systems.json and stations.json (with the skies', planets', asteroids' and stations' files)."""
    _export(run, export, rocks.EXPORTS)
    station_paths = {k: v for k, v in chorus_stations.mesh_paths(run('list', 'SM_MERGED_', capture=True).split()).items() if k in MODEL_SIZE}
    _export(run, export, [p for v in station_paths.values() for p in v] + [chorus_gate.GATE], 'all')
    resolver.prefetch(npcs.material_paths(export))
    resolver.fetch_textures(npcs.texture_paths(resolver, export), export)
    print('  the jumpgate...')
    gate = chorus_gate.build(export, mod, resolver)
    print('  the stations...')
    models = chorus_stations.build(export, mod, resolver, station_paths)
    print('  the skies...')
    skies = sky.build(export, mod, resolver, keys={s[5] for s in SYSTEMS})
    print('  the asteroids...')
    rock = rocks.build(export, mod, resolver)
    print('  the planets...')
    spheres = planets.build(export, mod, resolver, keys={s[4] for s in STATIONS})
    systems = []
    for sid, name, pos, sec, visible, sky_key, gates in SYSTEMS:
        e = {'id': sid, 'name': name, 'race': 0, 'security': sec, 'visible': visible, 'position': pos, 'sky': 4,
             'gates': gates, 'gateStation': f'{MOD}:{GATE_STATIONS[sid]}'}
        if sky_key in skies: e['skybox'] = skies[sky_key]
        if gate: e['jumpgate'] = gate   # (Chorus's own; Pescal Inartu's side of the route keeps the game's)
        systems.append(e)
    stations = []
    for tid, sid, name, tech, planet, looks in STATIONS:
        e = {'id': tid, 'system': f'{MOD}:{sid}', 'name': name, 'techLevel': tech, 'planet': 6, 'looksLike': looks}
        if planet in spheres: e['planetSphere'] = spheres[planet]
        if tid in models:
            e.update({'model': models[tid]['model'], 'materials': models[tid]['materials'], 'modelSize': MODEL_SIZE[tid]})
        orbit = _dressing(tid, rock, [e for e in (ships or []) if e['id'] in WRECK_HULLS], mod)
        if orbit: e['orbit'] = orbit
        stations.append(e)
    json.dump(systems, open(os.path.join(mod, 'systems.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(stations, open(os.path.join(mod, 'stations.json'), 'w', encoding='utf-8'), indent=1)
    print(f'  {len(systems)} systems, {len(stations)} stations')
    return systems, stations
