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


def static_mesh(path):
    """[(material name, {attribute: float32 array}, uint32 indices)] of the file's first mesh."""
    g, binary = load(path)
    mesh = g['meshes'][0]
    prims = []
    for p in mesh['primitives']:
        attrs = {k: read(g, binary, p['attributes'][k]).astype(np.float32) for k in KEEP if k in p['attributes']}
        idx = read(g, binary, p['indices']).reshape(-1).astype(np.uint32)
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


def save(path, prims, name='hull'):
    """Writes the primitives as one mesh on one root node, de-interleaved, 16-bit indices where they fit."""
    out = bytearray(); views = []; accs = []

    def add(arr, target, kind, comp):
        arr = np.ascontiguousarray(arr)
        while len(out) % 4: out.append(0)
        data = arr.tobytes()
        views.append({'buffer': 0, 'byteOffset': len(out), 'byteLength': len(data), 'target': target})
        out.extend(data)
        acc = {'bufferView': len(views) - 1, 'componentType': comp, 'count': int(arr.shape[0]), 'type': kind}
        if kind == 'VEC3' and target == 34962:
            acc['min'] = [float(v) for v in arr.min(0)]; acc['max'] = [float(v) for v in arr.max(0)]
        accs.append(acc)
        return len(accs) - 1

    materials, primitives = [], []
    for mat, attrs, idx in prims:
        a = {}
        for k in KEEP:
            if k in attrs:
                v = attrs[k].astype(np.float32)
                a[k] = add(v, 34962, {2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[v.shape[1]], 5126)
        small = int(idx.max()) < 65535
        i = add(idx.astype(np.uint16 if small else np.uint32), 34963, 'SCALAR', 5123 if small else 5125)
        if mat not in materials: materials.append(mat)
        primitives.append({'attributes': a, 'indices': i, 'material': materials.index(mat)})
    g = {'asset': {'version': '2.0', 'generator': 'chorus_ships_importer'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
         'nodes': [{'name': name, 'mesh': 0}], 'meshes': [{'name': name, 'primitives': primitives}],
         'materials': [{'name': m, 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.6}} for m in materials],
         'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(out)}]}
    while len(out) % 4: out.append(0)
    js = json.dumps(g, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(out)))
        f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js)
        f.write(struct.pack('<I4s', len(out), b'BIN\0')); f.write(out)
