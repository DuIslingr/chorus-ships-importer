# Blender: a ships.json "chorus" entry (the remake's GoF2/Hull ChorusLayers, tools/npcs.py TRIM_SHADER) as a node tree, for
# the contact sheet and previews (sheet_blender.py, render_blender.py). The palette by UV set 3 (its nearest texel), the
# tiling layer over UV set 1 (the plating's over UV set 0), the trim sheet's accent mask, occlusion, normal and emissive over
# UV set 0, metal and roughness from LayerData. Left out here: the tiling normal, the dirt and the far kicker (fine detail
# and distance effects a still at sheet size doesn't show).
import bpy


def _uv_names(mat):
    """The glTF importer's UV layer names (TEXCOORD_0 .. 3) on a mesh that uses this material."""
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(s.material == mat for s in o.material_slots):
            return [l.name for l in o.data.uv_layers]
    return []


def shell(nt, mat, c, img):
    """A "shell" (Guilt's M_Guilt_Shell) at rest: black, half metal, cut by its dissolve with the noise unflowed and the
    dither at its mean, ((mask.r + armsFade) x 0.5) x saturate(2 coverage - (1 - noise) x (1 - mask.g)^erode) >= 1/3; its
    glow (the tiled mask - emissiveExponent) x emissiveColor x emissiveIntensity (the centre's falloff left out)."""
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None or not c.get('mask'): return False
    N, L = nt.nodes, nt.links
    def math(op, a, bv=None, clamp=False):
        m = N.new('ShaderNodeMath'); m.operation = op; m.use_clamp = clamp
        for k, v in enumerate((a, bv)):
            if v is None: continue
            if isinstance(v, (int, float)): m.inputs[k].default_value = float(v)
            else: L.new(v, m.inputs[k])
        return m.outputs[0]
    def tex(rel, scale=1.0, colour=False):
        t = N.new('ShaderNodeTexImage'); t.image = img(rel, colour)
        if scale != 1.0:
            tc = N.new('ShaderNodeTexCoord'); vm = N.new('ShaderNodeVectorMath'); vm.operation = 'SCALE'; vm.inputs['Scale'].default_value = scale
            L.new(tc.outputs['UV'], vm.inputs[0]); L.new(vm.outputs['Vector'], t.inputs['Vector'])
        s_ = N.new('ShaderNodeSeparateColor'); L.new(t.outputs['Color'], s_.inputs['Color']); return s_.outputs
    A = tex(c['mask']); n = tex(c['noise'], float(c.get('tiling', 1.0)))[0] if c.get('noise') else 0.5
    erode = math('POWER', math('SUBTRACT', 1.0, A[1]), float(c.get('erode', 1.0)))
    cover = math('SUBTRACT', 2.0 * float(c.get('coverage', 0.5)), math('MULTIPLY', math('SUBTRACT', 1.0, n), erode), clamp=True)
    vis = math('MULTIPLY', math('MULTIPLY', math('ADD', A[0], float(c.get('armsFade', 1.0))), 0.5), cover)
    vis = math('SUBTRACT', vis, 1.0 - float(c.get('masterAlpha', 1.0)))
    L.new(math('GREATER_THAN', vis, 0.3333), b.inputs['Alpha'])
    for attr, val in (('blend_method', 'CLIP'), ('surface_render_method', 'DITHERED')):
        try: setattr(mat, attr, val)
        except Exception: pass
    for k in ('Base Color', 'Metallic', 'Roughness'):   # (the glTF import may have linked the vertex colours in)
        for l_ in list(b.inputs[k].links): L.remove(l_)
    b.inputs['Base Color'].default_value = [float(c.get('baseColor', 0.0))] * 3 + [1]
    b.inputs['Metallic'].default_value = float(c.get('metal', 0.5)); b.inputs['Roughness'].default_value = float(c.get('roughness', 0.5))
    k = float(c.get('emissiveIntensity', 0.0)) * float(c.get('emissionScale', 1.0))
    if k > 0 and float(c.get('emissiveExponent', 1.0)) < 1.0:
        At = tex(c['mask'], float(c.get('tiling', 1.0)))
        g = math('MAXIMUM', math('SUBTRACT', At[0], float(c['emissiveExponent'])), 0.0)
        col = c.get('emissiveColor') or [1, 0, 0]
        b.inputs['Emission Color'].default_value = list(col[:3]) + [1]
        L.new(math('MULTIPLY', g, k), b.inputs['Emission Strength'])
    mat.use_backface_culling = False
    return True


def apply(nt, mat, spec, img):
    c = spec['chorus']
    if c.get('kind') == 'shell': return shell(nt, mat, c, img)
    names = _uv_names(mat)
    if len(names) < 4 or not c.get('palette'): return False
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: return False
    N, L = nt.nodes, nt.links
    plating = c.get('kind') == 'plating'

    def uv(i):
        n = N.new('ShaderNodeUVMap'); n.uv_map = names[i]; return n.outputs['UV']

    def tex(rel, coords, colour=False, closest=False):
        t = N.new('ShaderNodeTexImage'); t.image = img(rel, colour)
        if closest: t.interpolation = 'Closest'
        L.new(coords, t.inputs['Vector']); return t

    def math(op, a, bv=None, clamp=False):
        m = N.new('ShaderNodeMath'); m.operation = op; m.use_clamp = clamp
        for k, v in enumerate((a, bv)):
            if v is None: continue
            if isinstance(v, (int, float)): m.inputs[k].default_value = float(v)
            else: L.new(v, m.inputs[k])
        return m.outputs[0]

    def mix(kind, fac, a, bv, clamp=False):
        m = N.new('ShaderNodeMix'); m.data_type = kind; m.clamp_result = clamp
        ins = {'FLOAT': (0, 2, 3), 'RGBA': (0, 6, 7)}[kind]
        for k, v in zip(ins, (fac, a, bv)):
            if isinstance(v, (int, float)): m.inputs[k].default_value = float(v)
            elif isinstance(v, (list, tuple)): m.inputs[k].default_value = list(v[:3]) + [1.0]
            else: L.new(v, m.inputs[k])
        return m.outputs[{'FLOAT': 0, 'RGBA': 2}[kind]]

    def sep(colour):
        s = N.new('ShaderNodeSeparateColor'); L.new(colour, s.inputs['Color']); return s.outputs

    # the palette: LayerColors left, LayerData right, read at their nearest texel (frac of UV set 3, as UE wraps it)
    xyz = N.new('ShaderNodeSeparateXYZ'); L.new(uv(3), xyz.inputs[0])
    u = math('MULTIPLY', math('FRACT', xyz.outputs['X']), 0.5)
    vfrac = math('FRACT', xyz.outputs['Y'])
    def at(offset):
        cmb = N.new('ShaderNodeCombineXYZ'); L.new(math('ADD', u, offset) if offset else u, cmb.inputs['X']); L.new(vfrac, cmb.inputs['Y'])
        return cmb.outputs[0]
    swatch = tex(c['palette'], at(0.0), closest=True).outputs['Color']
    data = sep(tex(c['palette'], at(0.5), closest=True).outputs['Color'])

    scale = N.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'; scale.inputs['Scale'].default_value = float(c.get('tiling', 1.0))
    L.new(uv(0 if plating else 1), scale.inputs[0]); tuv = scale.outputs['Vector']
    base = swatch
    if c.get('tilingDiffuse'):
        m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'MULTIPLY'; m.inputs[0].default_value = 1.0
        L.new(swatch, m.inputs[6]); L.new(tex(c['tilingDiffuse'], tuv, True).outputs['Color'], m.inputs[7]); base = m.outputs[2]
    rmo = sep(tex(c['tilingRmo'], tuv).outputs['Color']) if c.get('tilingRmo') else None
    rough_at = (rmo[1] if plating else rmo[0]) if rmo else 0.5
    metal_add = (rmo[2] if plating else rmo[1]) if rmo else 0.0
    ao = (rmo[0] if plating else rmo[2]) if rmo else 1.0
    metal = math('ADD', math('MULTIPLY', math('SUBTRACT', data[2], 0.5), 2.0), metal_add, clamp=True)
    rough = mix('FLOAT', rough_at, data[0], data[1])
    if not plating and c.get('trimAo'):
        aao = sep(tex(c['trimAo'], uv(0)).outputs['Color'])
        ao = math('MULTIPLY', ao, mix('FLOAT', float(c.get('aoIntensity', 1.0)), 1.0, aao[2])) if not isinstance(ao, float) else aao[2]
        if c.get('accentColor'):
            base = mix('RGBA', aao[0], base, c['accentColor'])
            metal = mix('FLOAT', aao[0], metal, float(c.get('accentMetal', 1.0)), clamp=True)
            rough = math('ADD', rough, math('MULTIPLY', aao[0], float(c.get('accentRoughness', 0.0))), clamp=True)
    if not isinstance(ao, float):   # (Principled has no occlusion: half of it on the colour)
        base = mix('RGBA', mix('FLOAT', 0.5, 1.0, ao), (0, 0, 0), base)
    L.new(base, b.inputs['Base Color']); L.new(metal, b.inputs['Metallic']); L.new(rough, b.inputs['Roughness'])
    nrm = c.get('tilingNormal') if plating else c.get('trimNormal')
    if nrm:
        nm = N.new('ShaderNodeNormalMap'); nm.uv_map = names[0]
        L.new(tex(nrm, tuv if plating else uv(0)).outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], b.inputs['Normal'])
    if not plating and c.get('trimEmissive') and c.get('emissiveAmount', 0) > 0:
        e = sep(tex(c['trimEmissive'], uv(0), True).outputs['Color'])
        acc = None
        for ch, key in enumerate(('emissiveR', 'emissiveG', 'emissiveB')):
            t = c.get(key) or [0, 0, 0]
            if max(t) <= 0: continue
            m = N.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'MULTIPLY'; m.inputs[0].default_value = 1.0
            m.inputs[6].default_value = list(t[:3]) + [1]
            cm = N.new('ShaderNodeCombineColor'); [L.new(e[ch], cm.inputs[k]) for k in range(3)]
            L.new(cm.outputs[0], m.inputs[7])
            if acc is None: acc = m.outputs[2]
            else:
                a = N.new('ShaderNodeMix'); a.data_type = 'RGBA'; a.blend_type = 'ADD'; a.inputs[0].default_value = 1.0
                L.new(acc, a.inputs[6]); L.new(m.outputs[2], a.inputs[7]); acc = a.outputs[2]
        if acc is not None:
            on = math('GREATER_THAN', xyz.outputs['Y'], 1.0) if c.get('emissiveUvShift') else 1.0
            strength = float(c['emissiveAmount']) * float(c.get('nearEmission', 1.0)) * float(c.get('emissionScale', 1.0))
            L.new(acc, b.inputs['Emission Color'])
            if isinstance(on, float): b.inputs['Emission Strength'].default_value = strength
            else: L.new(math('MULTIPLY', on, strength), b.inputs['Emission Strength'])
    return True
