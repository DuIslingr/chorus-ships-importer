# Run by import.py (--mobile) inside Blender, after the ES2 importer's: decimates the listed GLBs of the mod for phones,
# keeping the material names (the mod's materials find them by name), every UV set and the vertex colours (Chorus's
# layers read UV sets 0-3 and the dirt in the colours).
#   blender -b -P decimate_blender.py -- <list file> <src mod> <dst mod> <ratio> <min tris>
import bpy, os, sys
args = sys.argv[sys.argv.index('--') + 1:]
listing, src, dst, ratio, keep_below = args[0], args[1], args[2], float(args[3]), int(args[4])
files = [l.strip() for l in open(listing) if l.strip()]
# (the engine flames, glows, station lights and holograms: a few cards each, they vanish when collapsed; so does any
#  material with only a few triangles in the object)
KEEP_WHOLE = ('Thruster', 'Flame', 'Exhaust', 'Engine', 'Glow', 'Light', 'Holo', 'Billboard')
SMALL = 1500
before = after = 0


def decimate(ob):
    """One material's part: collapsed to the ratio (not below keep_below), or whole when small or a flame / light."""
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    name = ob.data.materials[0].name if ob.data.materials and ob.data.materials[0] else ''
    if tris <= max(keep_below, SMALL) or any(w in name for w in KEEP_WHOLE): return
    m = ob.modifiers.new('decimate', 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = max(ratio, keep_below / tris)
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)
    # (the imported custom normals don't survive the collapse: smooth by angle, as the hard-surface originals)
    bpy.ops.object.shade_smooth_by_angle(angle=0.6)


for i, rel in enumerate(files):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(src, rel))
    for ob in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
        before += sum(len(p.vertices) - 2 for p in ob.data.polygons)
        # each material on its own (one collapse over the whole object wiped some materials' faces out entirely)
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        if len(ob.data.materials) > 1:
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='MATERIAL'); bpy.ops.object.mode_set(mode='OBJECT')
        parts = [o for o in bpy.context.selected_objects if o.type == 'MESH']
        for part in parts: decimate(part)
        if len(parts) > 1:   # (back into one object: the model keeps its nodes)
            bpy.ops.object.select_all(action='DESELECT')
            for part in parts: part.select_set(True)
            bpy.context.view_layer.objects.active = parts[0]
            bpy.ops.object.join()
        after += sum(len(p.vertices) - 2 for p in bpy.context.view_layer.objects.active.data.polygons)
    out = os.path.join(dst, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_tangents=True, export_normals=True,
                              export_texcoords=True, export_vertex_color='ACTIVE', export_materials='EXPORT',
                              export_image_format='NONE', export_apply=True, export_yup=True, export_animations=False)
    print(f'decimate: {i + 1}/{len(files)} {rel}', flush=True)
print(f'decimate: done, {before} -> {after} triangles', flush=True)
