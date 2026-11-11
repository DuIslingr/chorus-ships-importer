# Blender script: the mod's shop icon (180 x 88, transparent, the ship seen from the front-left above) and preview.png,
# with the ships.json materials (colour, normal, metallic / smoothness, emission) as the remake draws them.
# blender -b --factory-startup -P render_blender.py -- <mod folder> <ship id>
import bpy, sys, os, json, math, mathutils

mod, ship_id = sys.argv[sys.argv.index('--') + 1:][:2]
ship = next(s for s in json.load(open(os.path.join(mod, 'ships.json'), encoding='utf-8')) if s['id'] == ship_id)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(mod, ship['model']))


def img(rel, colour=True):
    im = bpy.data.images.load(os.path.join(mod, rel))
    if not colour: im.colorspace_settings.name = 'Non-Color'
    return im


for spec in ship.get('materials', []):
    for mat in bpy.data.materials:
        if spec['material'].lower() not in mat.name.lower(): continue
        nt = mat.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
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
        if 'emission' in spec:
            t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['emission'])
            nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
            b.inputs['Emission Strength'].default_value = float(spec.get('emissionIntensity', 1)) * (0.25 if spec.get('engine') else 1)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
pts = [o.matrix_world @ mathutils.Vector(c) for o in meshes for c in o.bound_box]
lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (lo + hi) / 2; r = (hi - lo).length / 2
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.02, 0.02, 0.025)
for d, e in (((1, -1, 1.2), 4.0), ((-1, 1, 0.3), 1.2), ((0, 0, -1), 0.4)):
    l = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); l.data.energy = e
    l.rotation_euler = mathutils.Vector(d).to_track_quat('Z', 'Y').to_euler(); sc.collection.objects.link(l)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam


def shot(path, w, h, view, film_transparent, fill):
    """view: the direction the camera looks from (Blender frame of the import: nose +X, up +Z)."""
    cam.data.type = 'ORTHO'
    cam.location = ctr + mathutils.Vector(view).normalized() * r * 4
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = 2 * r * fill * max(1.0, w / h)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = film_transparent
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


sc.view_settings.exposure = 1.3
shot(os.path.join(mod, ship['icon']), 360, 176, (0.35, -1.0, 0.3), True, 0.3)
sc.view_settings.exposure = 0.0   # (import.py scales it to 180 x 88)
shot(os.path.join(mod, 'preview.png'), 960, 540, (0.8, -1.0, 0.55), False, 0.62)
