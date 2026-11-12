# GLB helpers: read an exported (CUE4Parse / FModel) skeletal mesh and write it again as a plain static mesh for the
# remake: only POSITION, NORMAL, TANGENT and TEXCOORD_0, no skin or joints (the remake shows skinned hulls in their rest
# pose anyway, Modding/README "New ships"), one primitive per material, materials named after the Unreal material instance.
import json, struct
import numpy as np

COMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
KEEP = ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0')


def load(path):
    b = open(path, 'rb').read()
    if b[:4] != b'glTF': raise ValueError(f'{path}: not a .glb')
    jl = struct.unpack_from('<I', b, 12)[0]
    g = json.loads(b[20:20 + jl])
    o = 20 + jl
    bl = struct.unpack_from('<I', b, o)[0]
    return g, b[o + 8:o + 8 + bl]


def read(g, binary, idx):
    a = g['accessors'][idx]; bv = g['bufferViews'][a['bufferView']]
    n, c = a['count'], COMP[a['type']]; dt = np.dtype(DT[a['componentType']])
    start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride') or c * dt.itemsize
    raw = np.frombuffer(binary, dtype=np.uint8, count=(n - 1) * stride + c * dt.itemsize, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(n, c * dt.itemsize), strides=(stride, 1))
    out = np.ascontiguousarray(rows).view(dt).reshape(n, c)
    if a.get('normalized') and dt.kind in 'iu': out = out.astype(np.float32) / np.iinfo(dt).max
    return out


def uv_frames(pos, uv, tris):
    """Per-triangle dP/du and dP/dv (T x 3 each) for the UV set uv (glTF UVs: v grows down the image)."""
    P, U = np.asarray(pos, np.float64)[tris], np.asarray(uv, np.float64)[tris]
    e1, e2, d1, d2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0], U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)[:, None]
    return (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r, (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r


def tangent_signs(pos, nrm, tan, uv, idx):
    """The tangents' handedness (w) from the UVs. glTF's bitangent is cross(normal, tangent) x w and points up the
    normal map (+Y, green), which is toward -v; CUE4Parse writes w = 1 everywhere, so on mirrored UV islands (a ship's
    other half) the normal maps' green came out inverted. -> tan with w recomputed (kept where the UVs are degenerate)."""
    tris = np.asarray(idx).reshape(-1, 3)
    _, B = uv_frames(pos, uv, tris)
    b = np.zeros((len(pos), 3))
    for k in range(3): np.add.at(b, tris[:, k], B)
    s = (np.cross(np.asarray(nrm, np.float64), np.asarray(tan, np.float64)[:, :3]) * -b).sum(-1)
    out = np.array(tan, np.float32)
    out[:, 3] = np.where(np.abs(s) < 1e-12, out[:, 3], np.sign(s))
    return out


def static_mesh(path, keep=KEEP):
    """[(material name, {attribute: float32 array}, uint32 indices)] of the file's first mesh (the attributes in `keep`;
    tangents with their handedness from the UVs, tangent_signs)."""
    g, binary = load(path)
    mesh = g['meshes'][0]
    prims = []
    for p in mesh['primitives']:
        attrs = {k: read(g, binary, p['attributes'][k]).astype(np.float32) for k in keep if k in p['attributes']}
        idx = read(g, binary, p['indices']).reshape(-1).astype(np.uint32)
        pa = p['attributes']
        if 'TANGENT' in attrs and all(k in pa for k in ('POSITION', 'NORMAL', 'TEXCOORD_0')):
            get = lambda k: attrs[k] if k in attrs else read(g, binary, pa[k]).astype(np.float32)
            attrs['TANGENT'] = tangent_signs(get('POSITION'), get('NORMAL'), attrs['TANGENT'], get('TEXCOORD_0'), idx)
        name = g['materials'][p['material']].get('name', f'material_{p["material"]}') if 'material' in p else 'default'
        prims.append((name, attrs, idx))
    return prims


def bounds(prims):
    pos = np.concatenate([a['POSITION'] for _, a, _ in prims])
    return pos.min(0), pos.max(0)


def joint_positions(path):
    """{joint node name: world position (glTF metres)} from the export's skeleton nodes (the bind pose)."""
    g, _ = load(path)
    nodes = g['nodes']; parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}

    def local(n):
        if 'matrix' in n: return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T
        T = np.eye(4); x, y, z, w = n.get('rotation', [0, 0, 0, 1])
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        T[:3, :3] = R * np.array(n.get('scale', [1, 1, 1])); T[:3, 3] = n.get('translation', [0, 0, 0])
        return T

    out = {}
    for i, n in enumerate(nodes):
        if 'name' not in n or 'mesh' in n: continue
        M = local(n); j = i
        while j in parent: j = parent[j]; M = local(nodes[j]) @ M
        out[n['name']] = M[:3, 3]
    return out


def save(path, prims, name='hull', nodes=None, keep=KEEP, split=False, quantize=False):
    """Writes the primitives as one mesh on one root node, de-interleaved, 16-bit indices where they fit; `nodes`
    {name: [x, y, z]} adds empty child nodes there (a weapon's "muzzle"); `keep` the attributes written (the Chorus
    layers' hulls: UV sets 0 - 3 and the vertex colours too). `split`: the primitives grouped by their attribute sets,
    each group its own mesh on a child node (a station's plain parts without the layers' four UV sets and colours).
    `quantize`: the normals and tangents as normalized bytes (KHR_mesh_quantization, required) and the vertex colours as
    normalized unsigned bytes, as Unreal keeps them (its tangent basis and vertex colours are 8-bit): about a third smaller;
    positions and UVs stay floats."""
    out = bytearray(); views = []; accs = []
    quantized = [False]

    def add(arr, target, kind, comp, normalized=False, stride=None, width=None):
        arr = np.ascontiguousarray(arr)
        while len(out) % 4: out.append(0)
        data = arr.tobytes()
        view = {'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data), 'target': target}
        if stride: view['byteStride'] = stride
        views.append(view)
        out.extend(data)
        acc = {'bufferView': len(views) - 1, 'componentType': comp, 'count': int(arr.shape[0]), 'type': kind}
        if normalized: acc['normalized'] = True
        if kind == 'VEC3' and target == 34962 and comp == 5126:
            acc['min'] = [float(v) for v in arr[:, :3].min(0)]; acc['max'] = [float(v) for v in arr[:, :3].max(0)]
        accs.append(acc)
        return len(accs) - 1

    def snorm8(v, width):   # (each element padded to 4 bytes: vertex attributes stay 4-byte aligned)
        q = np.round(np.clip(v, -1.0, 1.0) * 127.0).astype(np.int8)
        if q.shape[1] < width: q = np.concatenate([q, np.zeros((len(q), width - q.shape[1]), np.int8)], 1)
        return q

    materials, primitives, groups = [], [], {}
    for mat, attrs, idx in prims:
        a = {}
        for k in keep:
            if k in attrs:
                v = attrs[k].astype(np.float32)
                kind = {2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[v.shape[1]]
                if quantize and k in ('NORMAL', 'TANGENT'):
                    a[k] = add(snorm8(v, 4), 34962, kind, 5120, normalized=True, stride=4); quantized[0] = True
                elif quantize and k == 'COLOR_0':
                    c = np.round(np.clip(v, 0.0, 1.0) * 255.0).astype(np.uint8)
                    if c.shape[1] < 4: c = np.concatenate([c, np.full((len(c), 4 - c.shape[1]), 255, np.uint8)], 1)
                    a[k] = add(c, 34962, 'VEC4', 5121, normalized=True)
                else:
                    a[k] = add(v, 34962, kind, 5126)
        small = int(idx.max()) < 65535
        i = add(idx.astype(np.uint16 if small else np.uint32), 34963, 'SCALAR', 5123 if small else 5125)
        if mat not in materials: materials.append(mat)
        primitives.append({'attributes': a, 'indices': i, 'material': materials.index(mat)})
        groups.setdefault(tuple(sorted(a)), []).append(primitives[-1])
    if split and len(groups) > 1:
        meshes = [{'name': f'{name}_{k}', 'primitives': ps} for k, ps in enumerate(groups.values())]
        node_list = [{'name': name, 'children': list(range(1, len(meshes) + 1))}] + [{'name': m['name'], 'mesh': k} for k, m in enumerate(meshes)]
    else:
        meshes = [{'name': name, 'primitives': primitives}]
        node_list = [{'name': name, 'mesh': 0}]
    g = {'asset': {'version': '2.0', 'generator': 'chorus_ships_importer'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
         'nodes': node_list, 'meshes': meshes,
         'materials': [{'name': m, 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.6}} for m in materials],
         'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(out)}]}
    if quantized[0]: g['extensionsUsed'] = g['extensionsRequired'] = ['KHR_mesh_quantization']
    for n, pos in (nodes or {}).items():
        g['nodes'].append({'name': n, 'translation': [float(v) for v in pos]})
        g['nodes'][0].setdefault('children', []).append(len(g['nodes']) - 1)
    while len(out) % 4: out.append(0)
    js = json.dumps(g, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(out)))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(out), b'BIN\0')); f.write(out)
