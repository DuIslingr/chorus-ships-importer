# Blender script: one render of every ship in the built mod, with its materials as the remake draws them (render_blender's
# rules), for tools/sheet.py's contact sheet. A kit ship is drawn from its kit: the hull part, the kit's materials, its skin,
# and the kit's weapon models on its primary mounts (sheet.py names the weapon).
# blender -b --factory-startup -P sheet_blender.py -- <mod folder> <out folder> [<primary weapon model>]
import bpy, sys, os, json, mathutils

args = sys.argv[sys.argv.index('--') + 1:]
mod, out = args[0], args[1]
weapon = args[2] if len(args) > 2 else ''
K = 72.0   # game units per model metre (ships.py)
ships = json.load(open(os.path.join(mod, 'ships.json'), encoding='utf-8'))
kits = {k['id']: k for k in json.load(open(os.path.join(mod, 'shipkits.json'), encoding='utf-8'))} if os.path.exists(os.path.join(mod, 'shipkits.json')) else {}


def img(rel, colour=True):
    im = bpy.data.images.load(os.path.join(mod, rel), check_existing=True)
    if not colour: im.colorspace_settings.name = 'Non-Color'
    return im


def apply(specs):
    for spec in specs:
        for mat in bpy.data.materials:
            if spec['material'].lower() not in mat.name.lower() or not mat.node_tree: continue
            nt = mat.node_tree; b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b is None: continue
            if 'color' in spec: b.inputs['Base Color'].default_value = list(spec['color'][:3]) + [1]
            if 'diffuse' in spec:
                t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['diffuse']); nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
            if 'normal' in spec:
                t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['normal'], False)
                nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(t.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
            if 'metallicSmoothness' in spec:
                t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['metallicSmoothness'], False)
                sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(t.outputs['Color'], sep.inputs['Color'])
                nt.links.new(sep.outputs['Red'], b.inputs['Metallic'])
                inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
                nt.links.new(t.outputs['Alpha'], inv.inputs[1]); nt.links.new(inv.outputs['Value'], b.inputs['Roughness'])
            strength = float(spec.get('emissionIntensity', 1)) * (0.25 if spec.get('engine') else 1)
            if 'emission' in spec:
                t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['emission'])
                nt.links.new(t.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = strength
            elif 'emissionColor' in spec and spec.get('emissionIntensity'):
                b.inputs['Emission Color'].default_value = list(spec['emissionColor'][:3]) + [1]; b.inputs['Emission Strength'].default_value = strength


def load(path, game=(0, 0, 0)):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(mod, path))
    gx, gy, gz = game
    for o in set(bpy.data.objects) - before:
        if o.parent is None: o.location = (gz / K, gx / K, gy / K)   # game -> glTF (gz, gy, -gx) / K -> Blender (x, -z, y)


for ship in ships:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit = kits.get(ship.get('kit'))
    if kit:
        part = next(p for p in kit['parts'] if p['id'] == ship['build'].get('hull', kit['parts'][0]['id']))
        load(part['model'])
        if weapon:
            for m in ship.get('mounts', []):
                if m.get('slotType') == 0: load(weapon, m['position_engine'])
        apply(kit.get('materials', []))
        skin = next((s for s in kit.get('skins', []) if s['id'] == ship['build'].get('skin')), None)
        if skin: apply(skin['materials'])
    else:
        load(ship['model'])
        apply(ship.get('materials', []))
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    pts = [o.matrix_world @ mathutils.Vector(c) for o in meshes for c in o.bound_box]
    lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    ctr = (lo + hi) / 2; span = max(hi - lo)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.02, 0.02, 0.025)
    for d, e in (((1, -1, 1.2), 4.0), ((-1, 1, 0.3), 1.2), ((0, 0, -1), 0.4)):
        l = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); l.data.energy = e
        l.rotation_euler = mathutils.Vector(d).to_track_quat('Z', 'Y').to_euler(); sc.collection.objects.link(l)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    view = mathutils.Vector((0.8, -1.0, 0.55)).normalized()
    cam.location = ctr + view * span * 4; cam.rotation_euler = (-view).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = span * 10
    w, h = 800, 520
    sc.render.resolution_x, sc.render.resolution_y = w, h
    # Framed by the ship's outline as the camera sees it (a tall ship, the Omen's, fits by its height).
    rot = cam.rotation_euler.to_matrix()
    right, up = rot @ mathutils.Vector((1, 0, 0)), rot @ mathutils.Vector((0, 1, 0))
    xs = [(p - ctr).dot(right) for p in pts]; ys = [(p - ctr).dot(up) for p in pts]
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.08 * max(max(xs) - min(xs), (max(ys) - min(ys)) * w / h)
    cam.location += right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
    sc.render.film_transparent = True
    sc.render.filepath = os.path.join(out, ship['id'] + '.png')
    bpy.ops.render.render(write_still=True)
