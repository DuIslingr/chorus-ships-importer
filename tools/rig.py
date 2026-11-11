"""A rigidly skinned mesh (every vertex on one bone, as the Forsaken's) as a hierarchy of parts on its skeleton's nodes, with
Chorus's animations as glTF node animations, which the remake plays (its ModShipAnimator: ships.json "animations"). The
remake shows bones in their rest pose only; parts that move as objects animate.

  rigid_parts(src, prims)      the skeleton's nodes, and each bone's own vertices moved into that bone's frame (the
                               skin's inverse bind matrices), one mesh per bone
  clips(anim_jsons, names)     the exporter's `anim` samples (Unreal's frame, cm) -> glTF node channels: translation
                               (x, z, y) / 100, rotation (x, z, y, -w), as the exporter writes the skeleton's nodes
  save(path, nodes, roots, meshes, animations)
"""
import json, os, struct
import numpy as np
from . import glb


def rigid_parts(src, prims):
    """-> (nodes, roots, meshes): nodes [{name, translation, rotation, scale, children}] (the export's, without its skinned
    mesh node), roots (the scene's node indices), meshes {node index: [(material, attrs, indices)]}. prims: the same file's
    primitives as glb.static_mesh read them, in its order (their attributes already converted, tangent signs fixed)."""
    g, b = glb.load(src)
    skin = g['skins'][0]
    joints = skin['joints']
    ibm = glb.read(g, b, skin['inverseBindMatrices']).astype(np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)   # column-major
    mesh_nodes = {i for i, n in enumerate(g['nodes']) if 'mesh' in n}
    keep = [i for i in range(len(g['nodes'])) if i not in mesh_nodes]
    remap = {old: new for new, old in enumerate(keep)}
    nodes = []
    for i in keep:
        n = g['nodes'][i]
        e = {'name': n.get('name', f'node_{i}')}
        for k in ('translation', 'rotation', 'scale', 'matrix'):
            if k in n: e[k] = n[k]
        kids = [remap[c] for c in n.get('children', []) if c in remap]
        if kids: e['children'] = kids
        nodes.append(e)
    scene = g['scenes'][g.get('scene', 0)]
    roots = [remap[r] for r in scene['nodes'] if r in remap]

    meshes = {}
    src_prims = g['meshes'][0]['primitives']
    for (mat, attrs, idx), p in zip(prims, src_prims):
        J = glb.read(g, b, p['attributes']['JOINTS_0']).astype(np.int64)
        W = glb.read(g, b, p['attributes']['WEIGHTS_0']).astype(np.float64)
        owner = J[np.arange(len(J)), W.argmax(1)]                   # the skin joint each vertex hangs on (all rigid)
        tris = np.asarray(idx).reshape(-1, 3)
        tri_owner = owner[tris[:, 0]]
        for j in np.unique(tri_owner):
            t = tris[tri_owner == j]
            used, local = np.unique(t, return_inverse=True)
            M = ibm[j]; R = M[:3, :3]
            a = {}
            for k, v in attrs.items():
                v = np.asarray(v)[used]
                if k == 'POSITION': v = (v.astype(np.float64) @ R.T + M[:3, 3]).astype(np.float32)
                elif k == 'NORMAL':
                    v = v.astype(np.float64) @ R.T; v = (v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)).astype(np.float32)
                elif k == 'TANGENT':
                    xyz = v[:, :3].astype(np.float64) @ R.T
                    xyz /= np.maximum(np.linalg.norm(xyz, axis=1, keepdims=True), 1e-9)
                    v = np.concatenate([xyz, v[:, 3:]], 1).astype(np.float32)
                a[k] = v
            meshes.setdefault(remap[joints[j]], []).append((mat, a, local.reshape(-1).astype(np.uint32)))
    return nodes, roots, meshes


# Chorus's Forsaken (and the supercharged one: the same skeleton): its idle (the rest pose) and drift clips, in the order
# they go into the file (the first, idle, is what the remake loops when nothing else plays)
PHOENIX_ANIMS = 'SpacePrototype/Content/UnleashedPrototype/ArtAssets/Vehicles/Playerships/Phoenix/anims/phoenix_anim_'
CLIPS = {'idle': None, 'driftStart': PHOENIX_ANIMS + 'driftStart', 'driftLoop': PHOENIX_ANIMS + 'driftLoop',
         'driftEnd': PHOENIX_ANIMS + 'driftEnd', 'travelStart': PHOENIX_ANIMS + 'travelBoostBurst',
         'travelLoop': PHOENIX_ANIMS + 'travelBoostLoop', 'travelEnd': PHOENIX_ANIMS + 'travelBoostEnd'}
# poses laid over the state by the input (their last frame, weighted): the flaps (Chorus's additive steer / thrust / brake
# layers, folded onto the rest pose by the export); they key only the parts that move within them
POSES = {'steerL': PHOENIX_ANIMS + 'steerL', 'steerR': PHOENIX_ANIMS + 'steerR', 'thrusting': PHOENIX_ANIMS + 'thrusting',
         'brake': PHOENIX_ANIMS + 'brake', 'bankLeft': PHOENIX_ANIMS + 'bankingLeft', 'bankRight': PHOENIX_ANIMS + 'bankingRight',
         # the weapons deploying (a layer of their own) and the dash's rolls (once, over everything)
         'weaponsDeploy': PHOENIX_ANIMS + 'weaponsDeploy', 'weaponsDeployed': PHOENIX_ANIMS + 'weaponsDeployed',
         'weaponsUndeploy': PHOENIX_ANIMS + 'weaponsUndeploy',
         'dodgeStartLeft': PHOENIX_ANIMS + 'dodgeRollStartLeft', 'dodgeEndLeft': PHOENIX_ANIMS + 'dodgeRollEndLeft',
         'dodgeStartRight': PHOENIX_ANIMS + 'dodgeRollStartRight', 'dodgeEndRight': PHOENIX_ANIMS + 'dodgeRollEndRight',
         'driftDodgeLeft': PHOENIX_ANIMS + 'driftToDodgeLeft', 'driftDodgeRight': PHOENIX_ANIMS + 'driftToDodgeRight'}
# Chorus's own neutral pose on the animation side (phoenix_anim_Idle): what a layered clip is measured against
REFERENCE = PHOENIX_ANIMS + 'Idle'
# parts a layered clip leaves alone: the banking's roll of the whole ship (the remake banks the ship itself)
SKIP = {'bankLeft': {'BONE_SM_Phoenix_root1'}, 'bankRight': {'BONE_SM_Phoenix_root1'}}
ANIMATIONS = {'idle': 'idle', 'drift': {'start': 'driftStart', 'loop': 'driftLoop', 'end': 'driftEnd'},   # ships.json "animations"
              'travel': {'start': 'travelStart', 'loop': 'travelLoop', 'end': 'travelEnd'},
              'weapons': {'start': 'weaponsDeploy', 'loop': 'weaponsDeployed', 'end': 'weaponsUndeploy'},
              'steerLeft': 'steerL', 'steerRight': 'steerR', 'thrust': 'thrusting', 'brake': 'brake',
              'bankLeft': 'bankLeft', 'bankRight': 'bankRight',
              'dodgeLeft': {'start': 'dodgeStartLeft', 'end': 'dodgeEndLeft'}, 'dodgeRight': {'start': 'dodgeStartRight', 'end': 'dodgeEndRight'},
              'driftDodgeLeft': 'driftDodgeLeft', 'driftDodgeRight': 'driftDodgeRight'}
# the Forsaken's gun mounts ride its weapon platforms (ships.json mounts "follow")
FOLLOW = {'SM_Phoenix_wpnPlatform_01_l': 'BONE_SM_Phoenix_wpnPlatform_01_l', 'SM_Phoenix_wpnPlatform_01_r': 'BONE_SM_Phoenix_wpnPlatform_01_r'}
EXPORTS = [p for p in list(CLIPS.values()) + list(POSES.values()) + [REFERENCE] if p]


def load(folder):
    """{clip name: the exporter's anim JSON, None for the rest pose}, or None when the clips weren't exported."""
    out = {}
    for name, path in list(CLIPS.items()) + list(POSES.items()) + [('_reference', REFERENCE)]:
        if path is None: out[name] = None; continue
        f = os.path.join(folder, path.rsplit('/', 1)[1] + '.json')
        if not os.path.exists(f): return None
        out[name] = json.load(open(f, encoding='utf-8'))
    return out


def save_rigged(path, src, prims, anims, name='hull', keep_materials=None):
    """src's rigid parts on its skeleton with the clips (rig.load) -> path; keep_materials: only these materials' parts."""
    nodes, roots, meshes = rigid_parts(src, glb.static_mesh(src, keep=tuple(prims)) if isinstance(prims, tuple) else prims)
    if keep_materials is not None:
        meshes = {n: [p for p in ps if p[0] in keep_materials] for n, ps in meshes.items()}
        meshes = {n: ps for n, ps in meshes.items() if ps}
    save(path, nodes, roots, meshes, clips(anims, nodes, poses=set(POSES)), name)


def _ue_t(v): return [v[0] / 100.0, v[2] / 100.0, v[1] / 100.0]
def _ue_q(v): return [v[3], v[5], v[4], -v[6]]
def _ue_s(v): return [v[7], v[9], v[8]]


def clips(anims, nodes, rest_only='idle', tolerance=(0.002, 0.001), poses=()):
    """anims {clip name: the exporter's anim JSON (or None for a rest-pose clip)} -> [(name, [(node, path, times, values)])].
    Channels: the bones any clip moves (by more than tolerance: metres, quaternion components), every clip keying all of
    them so one clip's pose never lingers into the next; a None clip holds the rest pose (two keys, one second)."""
    by_name = {n['name']: i for i, n in enumerate(nodes)}
    sampled = {}
    moving = set()
    for name, d in anims.items():
        if d is None: continue
        frames = {}
        reference = name == '_reference'
        for bone, fr in d['bones'].items():
            if bone not in by_name: continue
            fr = np.asarray(fr, np.float64)
            T = np.array([_ue_t(f) for f in fr]); Q = np.array([_ue_q(f) for f in fr]); S = np.array([_ue_s(f) for f in fr])
            for k in range(1, len(Q)):                               # one hemisphere: LINEAR slerps the short way
                if np.dot(Q[k], Q[k - 1]) < 0: Q[k] = -Q[k]
            n = nodes[by_name[bone]]
            rt = np.array(n.get('translation', [0, 0, 0])); rq = np.array(n.get('rotation', [0, 0, 0, 1]))
            if name not in poses and not reference and (np.abs(T - rt).max() > tolerance[0] or min(np.abs(Q - rq).max(), np.abs(Q + rq).max()) > tolerance[1]):
                moving.add(bone)
            frames[bone] = (T, Q, S)
        sampled[name] = (frames, float(d['fps']), int(d['frames']))
    out = []
    for name, d in anims.items():
        if name == '_reference': continue
        channels = []
        if name in poses and d is not None:
            # a layered clip: only the parts it puts somewhere else than Chorus's own neutral pose (its Idle clip, the
            # reference: the launcher hinge sits 8 cm off the mesh's rest in every clip alike), past 1 cm / 0.003
            base = sampled.get('_reference')
            for bone, (T, Q, _) in sorted(sampled[name][0].items()):
                if bone in SKIP.get(name, ()): continue
                node = by_name[bone]; n = nodes[node]
                if base and bone in base[0]: rt, rq = base[0][bone][0][0], base[0][bone][1][0]
                else: rt = np.array(n.get('translation', [0, 0, 0])); rq = np.array(n.get('rotation', [0, 0, 0, 1]))
                dT = np.abs(T - rt).max(); dQ = max(min(np.abs(q - rq).max(), np.abs(q + rq).max()) for q in Q)
                if dT <= 0.01 and dQ <= 0.003: continue
                times = np.arange(len(T)) / sampled[name][1]
                channels.append((node, 'translation', times, T)); channels.append((node, 'rotation', times, Q))
            out.append((name, channels)); continue
        for bone in sorted(moving):
            node = by_name[bone]; n = nodes[node]
            rt = np.array(n.get('translation', [0, 0, 0]), np.float64); rq = np.array(n.get('rotation', [0, 0, 0, 1]), np.float64)
            if d is None or bone not in sampled[name][0]:
                times = np.array([0.0, 1.0] if d is None else [0.0, (sampled[name][2] - 1) / sampled[name][1]])
                T = np.stack([rt, rt]); Q = np.stack([rq, rq])
            else:
                T, Q, _ = sampled[name][0][bone]
                fps, count = sampled[name][1], sampled[name][2]
                times = np.arange(len(T)) / fps
            channels.append((node, 'translation', times, T))
            channels.append((node, 'rotation', times, Q))
        out.append((name, channels))
    return out


def save(path, nodes, roots, meshes, animations, name='hull'):
    """Writes the node hierarchy, a mesh on each node of `meshes`, and the animations, as a .glb."""
    out = bytearray(); views = []; accs = []

    def add(arr, target, kind, comp, minmax=False):
        arr = np.ascontiguousarray(arr)
        while len(out) % 4: out.append(0)
        data = arr.tobytes()
        v = {'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data)}
        if target: v['target'] = target
        views.append(v)
        out.extend(data)
        acc = {'bufferView': len(views) - 1, 'componentType': comp, 'count': int(arr.shape[0]), 'type': kind}
        if (kind == 'VEC3' and target == 34962) or minmax:
            a2 = arr.reshape(arr.shape[0], -1)
            acc['min'] = [float(x) for x in a2.min(0)]; acc['max'] = [float(x) for x in a2.max(0)]
        accs.append(acc)
        return len(accs) - 1

    nodes = [dict(n) for n in nodes]
    materials, gl_meshes = [], []
    for node, prims in sorted(meshes.items()):
        primitives = []
        for mat, attrs, idx in prims:
            a = {}
            for k in glb.KEEP:
                if k in attrs:
                    v = np.asarray(attrs[k], np.float32)
                    a[k] = add(v, 34962, {2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[v.shape[1]], 5126)
            small = int(idx.max()) < 65535
            i = add(idx.astype(np.uint16 if small else np.uint32), 34963, 'SCALAR', 5123 if small else 5125)
            if mat not in materials: materials.append(mat)
            primitives.append({'attributes': a, 'indices': i, 'material': materials.index(mat)})
        gl_meshes.append({'name': nodes[node]['name'] + '_mesh', 'primitives': primitives})
        nodes[node]['mesh'] = len(gl_meshes) - 1
    gl_anims = []
    for aname, channels in animations:
        samplers, chans = [], []
        for node, path_, times, values in channels:
            ti = add(np.asarray(times, np.float32).reshape(-1, 1), None, 'SCALAR', 5126, minmax=True)
            vi = add(np.asarray(values, np.float32), None, 'VEC4' if path_ == 'rotation' else 'VEC3', 5126)
            samplers.append({'input': ti, 'output': vi, 'interpolation': 'LINEAR'})
            chans.append({'sampler': len(samplers) - 1, 'target': {'node': node, 'path': path_}})
        gl_anims.append({'name': aname, 'samplers': samplers, 'channels': chans})
    # one root over the export's roots, named like a plain hull
    top = {'name': name, 'children': list(roots)}
    nodes.append(top)
    g = {'asset': {'version': '2.0', 'generator': 'chorus_ships_importer'}, 'scene': 0, 'scenes': [{'nodes': [len(nodes) - 1]}],
         'nodes': nodes, 'meshes': gl_meshes,
         'materials': [{'name': m, 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.6}} for m in materials],
         'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(out)}]}
    if gl_anims: g['animations'] = gl_anims
    while len(out) % 4: out.append(0)
    js = json.dumps(g, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(out)))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(out), b'BIN\0')); f.write(out)
