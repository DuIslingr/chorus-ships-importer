"""Chorus's stations as the remake's station models (stations.json "model" + "materials", Modding/README "Stations"): each
is rebuilt from its level's merged meshes (Maps/<region>/<level>_GeoLOD/SM_MERGED_<name>*: Chorus's HLOD proxies of the
station's actors, merged in the level's space at the origin), their materials converted as the ships' (tools/npcs.py:
Chorus's trim and plating layers drawn by the remake's GoF2/Hull, the rest their own maps), into one GLB centred on its
bounds. The cooked prefabs (PRE_*) carry no actors (Prefabricator's are editor-only), so the levels are the source.
"""
import json, os, struct
import numpy as np
from . import glb, npcs

UP = 'SpacePrototype/Content/UnleashedPrototype/'
# station id -> (the level's GeoLOD folder, the merged meshes' name prefix)
STATIONS = {
    'the_enclave': ('Maps/LocRSA/LocRSA02_GeoLOD', 'SM_MERGED_EnclavePartition'),
    'helios': ('Maps/LocTRN/LocTRN29_GeoLOD', 'SM_MERGED_Helios'),
    'eos': ('Maps/LocTRN/LocTRN31_GeoLOD', 'SM_MERGED_Eos'),
    'nimika_prime': ('Maps/LocASP/LocASP06_GeoLOD', 'SM_MERGED_'),   # (Nimika's ring station)
    'achunal_labs': ('Maps/LocMIF/LocMIF07_GeoLOD', 'SM_MERGED_'),   # (Tarris's big station, its tower and scaffolds)
}
SKIP = ('Decal', 'Interior', 'ForceField', 'Window', 'Traffic')   # (decals, the insides no one flies into, glass and
# shields, the traffic ships merged into a level)
# a station's triangles at most (Chorus's merged meshes are 2-4 million at LOD 0): the exporter writes every LOD
# (`export <list> <out> all`: <name>_LOD1.glb ...) and the largest meshes step down until the station fits
BUDGET = 350_000


def _tris(path):
    with open(path, 'rb') as h:
        h.read(12); n = struct.unpack('<I', h.read(4))[0]; h.read(4); g = json.loads(h.read(n))
    return sum(g['accessors'][p['indices']]['count'] // 3 for m in g['meshes'] for p in m['primitives'])


def pick_lods(export, meshes, budget=BUDGET):
    """Each mesh's file: the finest of its LODs, the largest stepping down first until the total fits the budget."""
    lods = []
    for p in meshes:
        files = [os.path.join(export, p + '.glb')] + [os.path.join(export, f'{p}_LOD{k}.glb') for k in range(1, 8)]
        files = [f for f in files if os.path.exists(f)]
        if files: lods.append([(f, _tris(f)) for f in files])
    at = [0] * len(lods)
    total = lambda: sum(l[i][1] for l, i in zip(lods, at))
    while total() > budget:
        steps = [(l[i][1] - l[i + 1][1], k) for k, (l, i) in enumerate(zip(lods, at)) if i + 1 < len(l)]
        if not steps: break
        at[max(steps)[1]] += 1
    return [l[i][0] for l, i in zip(lods, at)], total()


def _clustered(srcs):
    """The meshes round the station: one far from the rest is the level's own stray (Helios's billboard frames at the
    level's origin, the station 68 km off)."""
    boxes = []
    for f in srcs:
        P = np.concatenate([np.asarray(a['POSITION']) for _, a, _ in glb.static_mesh(f, keep=('POSITION',))])
        boxes.append((P.min(0), P.max(0)))
    centres = np.array([(lo + hi) / 2 for lo, hi in boxes])
    mid = np.median(centres, 0)
    spread = np.median(np.linalg.norm(centres - mid, axis=1)) + 1.0
    keep = [f for f, c in zip(srcs, centres) if np.linalg.norm(c - mid) < 10 * spread]
    for f in set(srcs) - set(keep): print(f'    (left out, far from the station: {os.path.basename(f)})')
    return keep


def mesh_paths(listing):
    """{station: [pak paths]} from the pak's SM_MERGED_ listing (exporter `list`)."""
    out = {}
    for sid, (folder, prefix) in STATIONS.items():
        out[sid] = sorted(p[:-len('.uasset')] for p in listing if p.endswith('.uasset') and f'{folder}/{prefix}' in p
                          and not any(k in p.rsplit('/', 1)[-1] for k in SKIP))
    return out


def build(export, mod, resolver, paths):
    """-> {station: {'model', 'materials', 'size'}} (size: the largest side in metres)."""
    out = {}
    os.makedirs(os.path.join(mod, 'models', 'stations'), exist_ok=True)
    os.makedirs(os.path.join(mod, 'maps', 'chorus'), exist_ok=True)
    for sid, meshes in paths.items():
        srcs, tris = pick_lods(export, meshes)
        srcs = _clustered(srcs)
        if not srcs: print(f'  station {sid}: not exported'); continue
        groups = [glb.static_mesh(s, keep=npcs.KEEP) for s in srcs]
        prims, mats = npcs._convert(export, mod, f'station_{sid}', groups, resolver, 2048)
        # (Chorus's layers read UV sets 0-3 and the vertex colours; the rest only position, normal, tangent and UV set 0)
        prims = [(m, {k: v for k, v in a.items() if m.endswith('__chorus') or k in glb.KEEP}, i) for m, a, i in prims]
        lo = np.min([np.asarray(a['POSITION']).min(0) for _, a, _ in prims], 0)
        hi = np.max([np.asarray(a['POSITION']).max(0) for _, a, _ in prims], 0)
        centre = (lo + hi) / 2
        for _, a, _ in prims: a['POSITION'] = (np.asarray(a['POSITION']) - centre).astype(np.float32)
        rel = f'models/stations/{sid}.glb'
        glb.save(os.path.join(mod, rel), prims, sid, keep=npcs.CHORUS_KEEP, split=True)
        size = float((hi - lo).max())
        out[sid] = {'model': rel, 'materials': mats, 'size': size}
        print(f'  station {sid}: {len(srcs)} meshes, {tris} triangles, {len(mats)} materials, {size:.0f} m across')
    return out
