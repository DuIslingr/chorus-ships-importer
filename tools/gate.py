"""Chorus's jumpgate (Core/FTLTravel/SM_MERGED_Jumpgate_001: a 9.7 km frame, a tunnel of rings about 490 m across at its
front end, the spine behind) as the Chorus systems' own gate (systems.json "jumpgate", Modding/README): its LODs picked to
a triangle budget as the stations' are, its materials converted as theirs (Chorus's trim and plating layers), its origin
moved into the ring tunnel's middle ("centre": false: where ships jump and come out; the model's +Z, away from the
spine, is the gate's front, the way ships leave).
"""
import os, shutil
import numpy as np
from PIL import Image
from . import glb, npcs, planets, stations

UP = 'SpacePrototype/Content/UnleashedPrototype/'
GATE = UP + 'Core/FTLTravel/SM_MERGED_Jumpgate_001'
BUDGET = 150_000
SIZE = 50000        # game units across its length (about 2.5 km: the game's gates are 15 000; the ring 2 500 units wide)
RING_RADIUS = 490   # metres, the ring tunnel's inside (measured: the 5th percentile of the front slab's distance off the axis)
# Chorus's FTL portal in the ring (the Theia gate's: its card and glow, M_FTL_Portal / M_FTL_PortalGlow on GoF2/ChorusPortal,
# a material's "portal" block): the cards turned to face along the tunnel and scaled so the wider one spans the ring
FTL = UP + 'Core/FTLTravel/'
PORTAL_CARDS = [(FTL + 'SM_FTL_PortalBorder', 'chorus_ftl_veins', FTL + 'MI_FTL_Portal'),
                (FTL + 'SM_FTL_PortalGlow', 'chorus_ftl_glow', FTL + 'MI_FTL_PortalGlow')]
VFX_ATLAS = UP + 'Effects/Curves/CA_BaseVFX'
EXPORTS = [c[0] for c in PORTAL_CARDS]


def _ring_centre(P):
    """The ring tunnel's middle: along the axis (z), the front part whose points all lie within the ring's outer radius
    after the struts' flare (the slabs past the widest one); x, y on the axis."""
    z = P[:, 2]
    edges = np.linspace(z.min(), z.max(), 41)
    widths = [np.abs(P[(z >= a) & (z < b), 0]).max() if ((z >= a) & (z < b)).any() else 0 for a, b in zip(edges, edges[1:])]
    k = int(np.argmax(widths))   # (the struts' widest slab: the tunnel starts past it)
    front = z >= edges[k + 1]
    return np.array([0.0, float(np.median(P[front, 1])), float((z[front].min() + z[front].max()) / 2)])


def _copy(export, mod, p, name):
    """A referenced texture (by its name in the material's graph) into maps/portal/. -> its path in the mod or None."""
    path = p.texture_paths.get(name)
    src = os.path.join(export, (path or '') + '.png')
    if not path or not os.path.exists(src): print(f'  gate: {name} not exported'); return None
    rel = f'maps/portal/{name.lower()}.png'
    os.makedirs(os.path.join(mod, 'maps', 'portal'), exist_ok=True)
    shutil.copyfile(src, os.path.join(mod, rel))
    return rel


def _curve(resolver, mod, row, name):
    """The CA_BaseVFX row as a 256 x 1 image (its colours as Unreal's curve atlas bakes them)."""
    rows = planets._atlas_rows(resolver, VFX_ATLAS)
    a = planets._curve_row(resolver, rows, row)
    rel = f'maps/portal/{name}_curve.png'
    os.makedirs(os.path.join(mod, 'maps', 'portal'), exist_ok=True)
    Image.fromarray(np.clip(np.round(a[None] * 255), 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(mod, rel))
    return rel


def _portal(export, mod, resolver):
    """The portal's prims (in the ring's plane, the gate's origin) and their materials."""
    prims, mats = [], []
    resolver.prefetch([c[2] for c in PORTAL_CARDS])
    ps = {mi: resolver.get(mi) for _, _, mi in PORTAL_CARDS}
    resolver.fetch_textures([t for p in ps.values() for t in p.texture_paths.values()], export)
    width = max(RING_RADIUS * 2, 1.0)
    span = None
    for mesh, name, mi in PORTAL_CARDS:
        src = os.path.join(export, mesh + '.glb')
        if not os.path.exists(src): print(f'  gate: {mesh} not exported'); return [], []
        for _, a, idx in glb.static_mesh(src, keep=glb.KEEP):
            P = np.asarray(a['POSITION'], np.float64)
            span = span or float(np.ptp(P[:, 2]))   # (the border card's longer side: it sets the scale of both)
            k = width / span
            turn = lambda v: np.stack([v[:, 2], v[:, 1], -v[:, 0]], 1)   # (a quarter turn about y: facing along the tunnel)
            a = dict(a, POSITION=(turn(P) * k).astype(np.float32), NORMAL=turn(np.asarray(a['NORMAL'])).astype(np.float32))
            a['TANGENT'] = npcs._tangents(a, idx, 'TEXCOORD_0')   # (the shader's bump offset and refraction need them)
            prims.append((name, a, idx))
        p = ps[mi]
        s_ = p.scalar
        if name == 'chorus_ftl_veins':   # (names apart: materials match by "name contains")
            block = {'kind': 'portal', 'noise': _copy(export, mod, p, p.textures.get('T_main') or 'T_Noise_Tiled03'),
                     'height': _copy(export, mod, p, 'T_SphericalGradient'), 'curve': _curve(resolver, mod, s_('FalloffCurve', 0), name),
                     'sphereNormal': _copy(export, mod, p, 'SphericalNormal_001'), 'ringNormal': _copy(export, mod, p, 'T_Circle_N'),
                     'tilingV': s_('Tiling V', 0.15), 'panningV': s_('Panning V', 0.33), 'structurePower': s_('Structure Power', 1.5),
                     'structureMult': s_('Structure Mult', 1.0), 'heightRatio': s_('HeightRatioInput', -1.0), 'fade': s_('FadeInAndOut', 1.0),
                     'ior': s_('IOR', 1.5), 'pulseSpeed': s_('VeinPulse_speed', -0.4), 'pulseB': s_('B', 3.0)}
        else:
            block = {'kind': 'glow', 'gradient': _copy(export, mod, p, 'T_Gradient_Vertical_04'), 'curve': _curve(resolver, mod, s_('FalloffCurve', 0), name),
                     'color': p.vector('Color1') or [1, 0, 0], 'lerpColor': s_('LerpColorParm', 1.0)}
        mats.append({'material': name, 'portal': {k: v for k, v in block.items() if v is not None}})
    return prims, mats


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
    portal, portal_mats = _portal(export, mod, resolver)
    prims += portal; mats += portal_mats
    rel = 'models/gates/chorus_gate.glb'
    os.makedirs(os.path.join(mod, 'models', 'gates'), exist_ok=True)
    glb.save(os.path.join(mod, rel), prims, 'chorus_gate', keep=npcs.CHORUS_KEEP, split=True)
    radius = round(RING_RADIUS * SIZE / length)
    print(f'  gate: {tris} triangles, {len(mats)} materials, ring at {centre.round(0).tolist()} m, jump radius {radius} units')
    return {'model': rel, 'size': SIZE, 'radius': radius, 'centre': False, 'materials': mats}
