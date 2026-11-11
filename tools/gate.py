"""Chorus's jumpgate (Core/FTLTravel/SM_MERGED_Jumpgate_001: a 9.7 km frame, a tunnel of rings about 490 m across at its
front end, the spine behind) as the Chorus systems' own gate (systems.json "jumpgate", Modding/README): its LODs picked to
a triangle budget as the stations' are, its materials converted as theirs (Chorus's trim and plating layers), its origin
moved into the ring tunnel's middle ("centre": false: where ships jump and come out; the model's +Z, away from the
spine, is the gate's front, the way ships leave).
"""
import os
import numpy as np
from . import glb, npcs, stations

UP = 'SpacePrototype/Content/UnleashedPrototype/'
GATE = UP + 'Core/FTLTravel/SM_MERGED_Jumpgate_001'
BUDGET = 150_000
SIZE = 50000        # game units across its length (about 2.5 km: the game's gates are 15 000; the ring 2 500 units wide)
RING_RADIUS = 490   # metres, the ring tunnel's inside (measured: the 5th percentile of the front slab's distance off the axis)


def _ring_centre(P):
    """The ring tunnel's middle: along the axis (z), the front part whose points all lie within the ring's outer radius
    after the struts' flare (the slabs past the widest one); x, y on the axis."""
    z = P[:, 2]
    edges = np.linspace(z.min(), z.max(), 41)
    widths = [np.abs(P[(z >= a) & (z < b), 0]).max() if ((z >= a) & (z < b)).any() else 0 for a, b in zip(edges, edges[1:])]
    k = int(np.argmax(widths))   # (the struts' widest slab: the tunnel starts past it)
    front = z >= edges[k + 1]
    return np.array([0.0, float(np.median(P[front, 1])), float((z[front].min() + z[front].max()) / 2)])


def build(export, mod, resolver):
    """-> systems.json "jumpgate" block, or None when the gate isn't exported."""
    srcs, tris = stations.pick_lods(export, [GATE], BUDGET)
    if not srcs: print('  gate: not exported'); return None
    prims, mats = npcs._convert(export, mod, 'chorus_gate', [glb.static_mesh(srcs[0], keep=npcs.KEEP)], resolver, 2048)
    prims = [(m, {k: v for k, v in a.items() if m.endswith('__chorus') or k in glb.KEEP}, i) for m, a, i in prims]
    P = np.concatenate([np.asarray(a['POSITION']) for _, a, _ in prims])
    centre = _ring_centre(P)
    for _, a, _ in prims: a['POSITION'] = (np.asarray(a['POSITION']) - centre).astype(np.float32)
    length = float(np.ptp(P, 0).max())
    rel = 'models/gates/chorus_gate.glb'
    os.makedirs(os.path.join(mod, 'models', 'gates'), exist_ok=True)
    glb.save(os.path.join(mod, rel), prims, 'chorus_gate', keep=npcs.CHORUS_KEEP, split=True)
    radius = round(RING_RADIUS * SIZE / length)
    print(f'  gate: {tris} triangles, {len(mats)} materials, ring at {centre.round(0).tolist()} m, jump radius {radius} units')
    return {'model': rel, 'size': SIZE, 'radius': radius, 'centre': False, 'materials': mats}
