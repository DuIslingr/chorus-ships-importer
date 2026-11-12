"""Chorus's Rift for the remake: the vortex (Effects/Meshes/SM_Rift_Vortex, a funnel about 28 m across, with M_PortalRift_2's
MI_PortalRift_2_LocAST_Outside: Nimika's dormant Rift) on the remake's GoF2/ChorusRift (a material's "rift" block, Modding/README):

- the Chorus systems' rift look (encounters.json "look" on the rift entry, tools/factions.py): the vortex at a rift run's
  centre, Chorus's FTL portal (the jumpgate's cards, tools/gate.py) opening between its stages, and the inner Rift's sky
  (T_Omen_InnerRift_Cubemap_Tex, the panorama CUE4Parse writes for the cube texture) while it lasts;
- the dormant Rift over Nimika Prime (an orbit prop, tools/world.py).

A rift run is fought inside the Rift (its look's sky is the inner Rift's), so the look's vortex is LocRFA's, the Rift seen
from inside: BP_LargeRift_LocRFA's SM_RiftMesh_LocRFA with MI_PortalRift_2_RFA_Outside (M_PortalRift_BOTTOM: the rift
block's "mode": "bottom"); the dormant Rift seen from Nimika keeps M_PortalRift_2's outside. Both heave as Chorus's vertex
shader moves them ("wpoMap" / "wpo": WP_Strenth in world centimetres over the BP's scale of that mesh, into the mesh's
metres).

The model is turned so its open face (the glb's +Y, Unreal's +Z) is the model's +Z: the look's models face the player, the
prop is turned to face the station. Its UVs stay Unreal's (v 1 at the middle); UV1 is a flat projection the cloud mask uses.
"""
import os, shutil, math
import numpy as np
from PIL import Image
from . import gate, glb, hdr, npcs, sky

UP = 'SpacePrototype/Content/UnleashedPrototype/'
VORTEX = UP + 'Effects/Meshes/SM_Rift_Vortex'
MI = UP + 'Effects/Portal/MI_PortalRift_2_LocAST_Outside'
INSIDE = UP + 'Effects/Meshes/SM_RiftMesh_LocRFA'
INSIDE_MI = UP + 'Effects/Portal/MI_PortalRift_2_RFA_Outside'
# the BPs' scale of each vortex mesh (BP_LargeRift_LocAST's SM_Rift_Vortex, BP_LargeRift_LocRFA's SM_RiftMesh_LocRFA), across
SCALE = {MI: 70000.0, INSIDE_MI: 43000.0}
INNER_SKY = UP + 'ArtAssets/Environment/FactionJantu/InnerRift/T_Omen_InnerRift_Cubemap_Tex'
EXPORTS = [VORTEX, INSIDE]
# the textures the material reads that aren't parameters (its graph's own: the slots' order in the compiled shader)
HARD_WIRED = {'strip': 'T_NoiseStrip_B', 'cloud': 'T_Cloud_03'}
SLOTS = {'tiled': 'T_Tiled', 'lightning': 'Param', 'cloudMask': 'T_Cloudmask_Flipbook', 'rock': 'T_Tiled2'}
# Chorus's HDR to the remake's: the vortex's brightest 1 % (about 5, measured over the mesh with the decoded shader) near 2
EXPOSURE = 0.4
SKY_SIZE = (2048, 1024)
KEEP = ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1')
LOOK_RIFT_SIZE, LOOK_PORTAL_SIZE = 30000, 8000


def _copy(export, mod, p, name):
    path = p.texture_paths.get(name)
    src = os.path.join(export, (path or '') + '.png')
    if not path or not os.path.exists(src): print(f'  rift: {name} not exported'); return None
    rel = f'maps/rift/{name.lower()}.png'
    os.makedirs(os.path.join(mod, 'maps', 'rift'), exist_ok=True)
    shutil.copyfile(src, os.path.join(mod, rel))
    return rel


def material(export, mod, resolver, name='chorus_rift', mi_path=MI, extent_cm=None):
    """The vortex's "rift" material entry (its maps copied into maps/rift/); M_PortalRift_BOTTOM's instances as "bottom"
    (extent_cm: the mesh's width in Chorus's world, its fades' scale to the look's size)."""
    resolver.prefetch([mi_path])
    p = resolver.get(mi_path)
    if p is None: return None
    resolver.fetch_textures(list(p.texture_paths.values()), export)
    s = p.scalar
    def v(n, d): c = p.vector(n); return [round(float(x), 6) for x in (c or d)[:3]]
    block = {k: _copy(export, mod, p, p.textures.get(slot)) for k, slot in SLOTS.items()}
    block.update({k: _copy(export, mod, p, t) for k, t in HARD_WIRED.items()})
    block.update({
        'mainUV': [s('ucoord_Main', 1.5), s('Vcoord_Main', 1), s('Upannel_Main', 0.01), s('Vpannel_Main', 0.03)],
        'detailUV': [s('ucoord', 1), s('Vcoord', 1.5), s('Upannel', 0), s('Vpannel', 0.02)],
        'cloudsUV': [s('Ucoord_Parallax', 2), s('Vcoord_Parallax', 1), s('Upannel_Parallax', 0.018), s('Vpannel_Parallax', 0.02)],
        # (the graph's second rock read takes the first's tiling and pan too: Tiled2_2's own are unused)
        'rockUV': [s('ucoord_Tiled2', 3), s('Vcoord_Tiled2', 1), s('Upannel_Tiled2', 0.009), s('Vpannel_Tiled2', 0.018)],
        'detailOffset': [s('Uposition', 0.4), s('Vposition', 0.4)],
        'heightPan': [s('Upannel_Parallax_Height', 0.018), s('Vpannel_Parallax_Height', 0.02)],
        'mainPow': s('Acc_pow_Main', 0.7), 'detailPow': s('pow', 7), 'detailMul': s('mul', 1), 'redCenter': s('mul_RedCenter', 1794),
        'cloudsPow': s('Acc_pow_Parallax', 2), 'heightRatio': s('Height Ratio', 1.5), 'cloudPow': s('pow_parallax', 15),
        'cloudMul': s('mul_Parallax', 100), 'boltSpeed': s('Bolt_Speed', 0.1), 'pulseRate1': s('Pulse_Rate_Bolts 1', 0.05),
        'pulseRate2': s('Pulse_Rate_Bolts 2', 0.02), 'sequenceTime': s('Bolt Sequence Time', 0.1),
        'frames': s('Number of R/C_Lighting', 4), 'lightningMul': s('mul_lightning', 100000), 'lightningCloud': s('mul_lightning_Cloud', 200),
        'gradation': s('pow_Gradation', 4), 'blendExp': s('Color Blend Exp', 1), 'blendMult': s('Color Blend Mult', 1),
        'corePow': s('Pow_Lighthing', 35), 'coreTint': s('LightingCoreTint', 0.05),
        'inner': v('Color Inner', [0.1, 0, 0.003]), 'outer': v('Color Outer', [0.1, 0, 0.0333]), 'core': v('Lighthing_Core', [0, 0, 0]),
        'brightness': v('Color_Brightness', [200, 0.8, 5]), 'background': v('Color Background', [0.01, 0.013, 0.02]),
        'clouds': v('Color Clouds', [0.0064, 0.0061, 0.02]), 'exposure': EXPOSURE})
    # the vertex shader's offset: WP_Strenth (world cm) over the BP's scale of the mesh, in its metres
    wpo_map = p.textures.get('T_WorldPosition')
    if wpo_map and s('WP_Strenth', 0) > 0:
        block['wpoMap'] = _copy(export, mod, p, wpo_map)
        block['wpo'] = [round(s('WP_Strenth', 0) / SCALE.get(mi_path, 70000.0) / 100.0, 6), s('ucoord_WP', 1), s('Vcoord_WP', 2),
                        s('Upannel_WP', 0.01), s('Vpannel_WP', 0.04)]
    if p.chain and p.chain[-1] == 'M_PortalRift_BOTTOM':
        # the Rift from inside: its own colours, blended, its fades in game units at the look's size
        k = LOOK_RIFT_SIZE / extent_cm if extent_cm else 0.0
        block.update({'mode': 'bottom', 'emissive': v('Emmisive_Color', [0.05, 0.0075, 0.0088]),
                      'baseColor': v('Base_Color', [0.05, 0.0097, 0.0092]),
                      'depthFade': round(s('Dapthfade', 0) * k, 1), 'fadeOffset': round(s('Fade Offset', 0) * k, 1),
                      'fadeLength': round(s('Fade Length (S)', 0) * k, 1)})
        for key in ('inner', 'outer', 'background', 'clouds'): block.pop(key, None)
    if not block['tiled']: return None
    return {'material': name, 'rift': {k: (round(float(x), 6) if isinstance(x, float) else x) for k, x in block.items() if x is not None}}


def model(export, mod, mesh=VORTEX, name='chorus_rift'):
    """models/rift/<name>.glb: the vortex turned to face +Z, centred (its material named 'name'). -> its path in the mod or
    None."""
    src = os.path.join(export, mesh + '.glb')
    if not os.path.exists(src): print(f'  rift: {mesh.rsplit("/", 1)[1]} not exported'); return None
    turn = lambda v: np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1)   # (a quarter turn about x: the glb's +y to +z)
    prims = []
    for _, a, idx in glb.static_mesh(src, keep=('POSITION', 'NORMAL', 'TEXCOORD_0', 'TEXCOORD_1')):
        P = turn(np.asarray(a['POSITION'], np.float64))
        a = dict(a, POSITION=P.astype(np.float32), NORMAL=turn(np.asarray(a['NORMAL'])).astype(np.float32))
        a['TANGENT'] = npcs._tangents(a, idx, 'TEXCOORD_0')   # (the clouds' bump offset)
        if 'TEXCOORD_1' not in a: a['TEXCOORD_1'] = a['TEXCOORD_0']
        prims.append([name, a, idx])
    P = np.concatenate([p[1]['POSITION'] for p in prims])
    mid = (P.min(0) + P.max(0)) / 2
    for p in prims: p[1]['POSITION'] = (p[1]['POSITION'] - mid).astype(np.float32)
    rel = f'models/rift/{name}.glb'
    os.makedirs(os.path.join(mod, 'models', 'rift'), exist_ok=True)
    glb.save(os.path.join(mod, rel), [tuple(p) for p in prims], name, keep=KEEP)
    return rel


def _extent_cm(export, mesh, mi_path):
    """The mesh's width in Chorus's world (its glb metres x 100 x the BP's scale), or None."""
    src = os.path.join(export, mesh + '.glb')
    if not os.path.exists(src): return None
    lo, hi = glb.bounds(glb.static_mesh(src))
    return float(max(hi[0] - lo[0], hi[2] - lo[2])) * 100.0 * SCALE.get(mi_path, 1.0)


def portal(export, mod, resolver):
    """models/rift/chorus_rift_portal.glb: Chorus's FTL portal cards alone (facing +Z) and their materials, or (None, [])."""
    prims, mats = gate._portal(export, mod, resolver)
    if not prims: return None, []
    rel = 'models/rift/chorus_rift_portal.glb'
    os.makedirs(os.path.join(mod, 'models', 'rift'), exist_ok=True)
    glb.save(os.path.join(mod, rel), prims, 'chorus_rift_portal', keep=glb.KEEP, split=True)
    return rel, mats


def inner_sky(run, export, mod):
    """The inner Rift's sky: its cube texture's panorama as the systems.json-style "skybox" block, or None."""
    src = os.path.join(export, INNER_SKY + '.hdr')
    if not os.path.exists(src):
        lst = os.path.join(export, '..', 'rift_list.txt')
        open(lst, 'w').write(INNER_SKY + '\n')
        run('export', lst, export, capture=True)
    if not os.path.exists(src): print('  rift: the inner Rift sky not exported'); return None
    pano = hdr.read(src)[..., :3]
    # (up to the panoramas' size: each channel resized as floats)
    pano = np.stack([np.asarray(Image.fromarray(pano[..., c].astype(np.float32), 'F').resize(SKY_SIZE, Image.BICUBIC)) for c in range(3)], -1)
    pano = np.maximum(pano, 0)
    top = float(np.percentile(pano.max(-1), 99.5)) or 1.0
    enc = np.clip(np.round(sky._linear_to_srgb(np.clip(pano / top, 0, 1)) * 255), 0, 255).astype(np.uint8)
    rel = 'skies/inner_rift.png'
    os.makedirs(os.path.join(mod, 'skies'), exist_ok=True)
    Image.fromarray(enc, 'RGB').save(os.path.join(mod, rel), optimize=True)
    return {'nebula': rel, 'stars': 'none', 'nebulaBrightness': round(top, 4)}


def facing(at):
    """A prop's rotation (Unity Euler degrees) turning its +Z from 'at' (game units) to the orbit's middle."""
    d = np.array([-at[0], -at[1], at[2]], np.float64)   # (to the origin, in Unity's frame: game z is Unity -z)
    d /= np.linalg.norm(d)
    return [round(math.degrees(-math.asin(d[1])), 2), round(math.degrees(math.atan2(d[0], d[2])), 2), 0]


def build(run, export, mod, resolver, systems):
    """-> (the rift look for encounters.json or None, the dormant Rift's (prop, material) or None)."""
    mat = material(export, mod, resolver)
    rel = model(export, mod) if mat else None
    if not rel: return None, None
    portal_rel, portal_mats = portal(export, mod, resolver)
    # the run's vortex: the Rift from inside (LocRFA's, M_PortalRift_BOTTOM), else the outside one
    inside = material(export, mod, resolver, 'chorus_rift_inside', INSIDE_MI, _extent_cm(export, INSIDE, INSIDE_MI))
    inside_rel = model(export, mod, INSIDE, 'chorus_rift_inside') if inside else None
    run_rel, run_mat = (inside_rel, inside) if inside_rel else (rel, mat)
    look = {'systems': systems, 'rift': {'model': run_rel, 'size': LOOK_RIFT_SIZE}, 'materials': [run_mat] + portal_mats}
    if portal_rel: look['portal'] = {'model': portal_rel, 'size': LOOK_PORTAL_SIZE}
    s = inner_sky(run, export, mod)
    if s: look['skybox'] = s
    print(f'  rift: the vortex{" (from inside)" if inside_rel else ""}, {"the portal, " if portal_rel else ""}{"the inner sky" if s else "no sky"}')
    return look, (rel, mat)
