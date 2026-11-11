# Blender script: the mod's shop icon (180 x 88, transparent, the ship seen from the front-left above) and preview.png,
# with the ships.json materials (colour, normal, metallic / smoothness, emission) as the remake draws them.
# blender -b --factory-startup -P render_blender.py -- <mod folder> <ship id> [<preview file name>]
import bpy, sys, os, json, math, mathutils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chorus_blender   # (a ships.json "chorus" entry: Chorus's layers as the remake draws them)

args = sys.argv[sys.argv.index('--') + 1:]
mod, ship_id = args[:2]
preview = args[2] if len(args) > 2 else 'preview.png'   # '' = the icon only
ship = next(s for s in json.load(open(os.path.join(mod, 'ships.json'), encoding='utf-8')) if s['id'] == ship_id)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(mod, ship['model']))


def additive(nt, mat, spec, img):
    """An additive glow layer (ships.json "additive": true), as the remake draws it: unlit light added to what is behind,
    the emission texture (else the diffuse) x emissionIntensity."""
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    em = nt.nodes.new('ShaderNodeEmission'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); add = nt.nodes.new('ShaderNodeAddShader')
    em.inputs['Color'].default_value = list(spec.get('emissionColor', spec.get('color', [1, 1, 1])))[:3] + [1]
    em.inputs['Strength'].default_value = float(spec.get('emissionIntensity', 1))
    tex = spec.get('emission') or spec.get('diffuse')
    if tex:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex); nt.links.new(t.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1]); nt.links.new(add.outputs[0], out.inputs['Surface'])
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED')):
        try: setattr(mat, attr, val)
        except Exception: pass


def img(rel, colour=True):
    im = bpy.data.images.load(os.path.join(mod, rel))
    if not colour: im.colorspace_settings.name = 'Non-Color'
    return im


for spec in ship.get('materials', []):
    for mat in bpy.data.materials:
        if spec['material'].lower() not in mat.name.lower(): continue
        nt = mat.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        if spec.get('additive') or spec.get('shimmer'):
            additive(nt, mat, spec, img); continue
        if spec.get('chorus'):
            chorus_blender.apply(nt, mat, spec, img); continue
        if 'color' in spec: b.inputs['Base Color'].default_value = list(spec['color'][:3]) + [1]
        if 'diffuse' in spec:
            t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(spec['diffuse']); nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
            if spec.get('alphaClip'):   # (cut out below the clip, as the remake draws decals)
                gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = float(spec['alphaClip'])
                nt.links.new(t.outputs['Alpha'], gt.inputs[0]); nt.links.new(gt.outputs['Value'], b.inputs['Alpha'])
                for attr, val in (('blend_method', 'CLIP'), ('surface_render_method', 'DITHERED')):
                    try: setattr(mat, attr, val)
                    except Exception: pass
        if 'smoothness' in spec: b.inputs['Roughness'].default_value = 1.0 - float(spec['smoothness'])
        if spec.get('metallic', -1) >= 0: b.inputs['Metallic'].default_value = float(spec['metallic'])
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
span = max(hi - lo)   # the longest side: the framing follows it (a long hull isn't cropped more than a round one)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
sc.view_settings.view_transform = 'Standard'   # (the remake has bloom and no tonemapping: a bright red glow stays red)
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
    cam.data.ortho_scale = span * fill
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = film_transparent
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


sc.view_settings.exposure = 1.3
shot(os.path.join(mod, ship['icon']), 360, 176, (0.35, -1.0, 0.3), True, 0.875)
sc.view_settings.exposure = 0.0   # (import.py scales it to 180 x 88)
if preview: shot(os.path.join(mod, preview), 960, 540, (0.8, -1.0, 0.55), False, 1.57)
