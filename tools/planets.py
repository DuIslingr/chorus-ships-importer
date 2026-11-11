"""Chorus's planets (ArtAssets/Environment/Planets) as the remake's stations.json "planetSphere" with "look": "chorus"
(GoF2/ChorusPlanet, GoF2/ChorusAtmosphere; Modding/README "Chorus planets"): each region's planet material resolved through
its parents, its maps copied, the CA_Planets curve atlas rows it reads baked into a small image (rows: elevation colour,
atmosphere directional colour, atmosphere fresnel colour; a shell's: directional, fresnel), its values by Chorus's
parameter names and its static switches.

    M_Planet03 ("surface"): Has Water, Has Clouds?, Enable Macro Normalmap, Macro As Height Treshold, Roughness | Use
      Constant, Modify Shaded Specular; with "Is Atmosphere Shell?" it is the atmosphere ("chorusAtmosphere").
    M_Planet_SurfaceCheap ("cheap"): Use Simple.

The curves are Unreal's rich curves (linear, constant or cubic keys with their tangents), evaluated as its curve atlas
bakes them (256 texels across, constant beyond the first and last key).
"""
import json, os, shutil
import numpy as np
from PIL import Image

UP = 'SpacePrototype/Content/UnleashedPrototype/'
PLANETS = UP + 'ArtAssets/Environment/Planets/'
CURVE_ATLAS = PLANETS + 'CA_Planets'
# (key, surface material, atmosphere shell material or None): the regions' planets
REGION_PLANETS = [
    ('stega_giant', 'MI_Planet_LocRSA_bigPlanet', None),
    ('stega_world', 'MI_Planet_LocRSA', 'MI_Planet_LocRSA_Atmosphere'),
    ('stega_moon', 'MI_Planet_LocRSA_simple', None),
    ('amarok_world', 'MI_Planet_LocTRN', 'MI_Planet_LocTRN_Atmosphere'),
    ('nimika_world', 'MI_Planet03c', 'MI_Planet03c_Atmosphere_LocAST'),
    ('tarris_world', 'MI_Planet_LocLAB', 'MI_Planet_LocLAB_Atmosphere'),
    ('tarris_giant', 'MI_Planet_LocLab_bigPlanet', None),
    ('tarris_moon', 'MI_Planet_LocLAB_smallPlanet', None),
]
SURFACE_MAPS = {'terrainNormal': 'Terrain Normalmap', 'macroNormal': 'Macro | Normalmap', 'macroHeight': 'Macro | Heightmap',
                'terrainHeight': 'Terrain Heightmap', 'grunge': 'Grunge | Texture', 'clouds': 'Clouds 01',
                'cloudsFlow': 'Clouds Flowmap', 'flowNoise': 'Flowmap Time Noise'}
CHEAP_MAPS = {'normal': 'Normal', 'diffuse': 'DiffuseTexture', 'night': 'NightTexture', 'clouds': 'CloudsTextures'}
SURFACE_VALUES = ['Tiling | Terrain Base', 'Tiling | Macro Tile Factor', 'Grunge | Tiling Factor', 'PanSpeed | Terrain',
                  'Terrain | Normal Intensity', 'Macro | Normal Intensity', 'Macro | Treshold', 'Macro | Treshold Contrast',
                  'Atmosphere Fresnel Exp', 'Atmosphere Fresnel Base', 'Terminator Tightness (for Opacity)', 'Atmosphere Clouds Emissive',
                  'Atmosphere Directional Emissive', 'Fresnel Lit Intensity', 'Fresnel Shade Intensity', 'Atmosphere Fresnel Emissive',
                  'Overall Brightness Lit Side', 'Overall Brightness Shadowed Side', 'Overall Specular Shadowed Side',
                  'Roughness | Grunge/Height Balance', 'Color | Dimming Factor', 'Grunge | Intensity', 'Atmosphere Roughness',
                  'Macro | Color Influence', 'Water Level', 'Water Density', 'Underwater Normal Intensity', 'Terrain Macro Height Strength',
                  'Water Metallic', 'Water Specular', 'Water Roughness', 'Roughness | Constant', 'Tiling Clouds', 'PanSpeed_Clouds',
                  'Cloud Coverage', 'Cloud Contrast', 'Flowmap Tiling', 'PanSpeed_CloudsFlow', 'Flowmap Speed', 'Flowmap Offsets',
                  'Flowmap Noise Tiling', 'Flowmap Noise', 'Flowmap Mip Level', 'Clouds Brightness Min', 'Clouds Emissive']
SURFACE_COLOURS = ['Water Color Deep', 'Water Color Shallow', 'Clouds Tint', 'Overall Basecolor Tint', 'Overall Emissive Tint']
CHEAP_VALUES = ['PlanetSpeed', 'CloudSpeed', 'NightIntensity', 'Normal Intensity', 'AreaCoverage', 'AreaContrast', 'RimContrast', 'BlueRimContrast']
CHEAP_COLOURS = ['InsideColor', 'RimColor', 'BlueRimColor']
SHELL_VALUES = ['PlanetRadiusUU', 'AtmosphereHeightUU', 'AtmosphereExponent', 'Terminator Tightness (for Opacity)',
                'Atmosphere Directional Emissive', 'Atmosphere Fresnel Exp', 'Atmosphere Fresnel Base', 'Atmosphere Fresnel Emissive',
                'Fresnel Lit Intensity', 'Fresnel Shade Intensity', 'Overall Brightness Lit Side', 'Overall Brightness Shadowed Side']
ATLAS_WIDTH = 256


# ---- Unreal's rich curves ---------------------------------------------------------------------------------------------

def _eval(keys, t):
    """FRichCurve::Eval: constant before the first key and after the last; linear, constant or cubic (Hermite by the keys'
    leave / arrive tangents) between."""
    if not keys: return 0.0
    if t <= keys[0]['Time']: return float(keys[0]['Value'])
    if t >= keys[-1]['Time']: return float(keys[-1]['Value'])
    for a, b in zip(keys, keys[1:]):
        if a['Time'] <= t <= b['Time']:
            dt = b['Time'] - a['Time']
            if dt <= 0: return float(b['Value'])
            x = (t - a['Time']) / dt
            mode = a.get('InterpMode', 'RCIM_Linear')
            if mode == 'RCIM_Constant': return float(a['Value'])
            if mode == 'RCIM_Linear': return float(a['Value'] + (b['Value'] - a['Value']) * x)
            p0, p3 = a['Value'], b['Value']
            p1 = p0 + a.get('LeaveTangent', 0.0) * dt / 3.0
            p2 = p3 - b.get('ArriveTangent', 0.0) * dt / 3.0
            u = 1 - x
            return float(u ** 3 * p0 + 3 * u * u * x * p1 + 3 * u * x * x * p2 + x ** 3 * p3)
    return float(keys[-1]['Value'])


def _atlas_rows(resolver):
    resolver.prefetch([CURVE_ATLAS])
    atlas = json.load(open(resolver._file(CURVE_ATLAS), encoding='utf-8'))
    curves = next(e['Properties']['GradientCurves'] for e in atlas if e.get('Type') == 'CurveLinearColorAtlas')
    return [c['ObjectPath'].rsplit('.', 1)[0] if c else None for c in curves]


def _curve_row(resolver, rows, index):
    """One atlas row (ATLAS_WIDTH x rgba, linear) of the curve at 'index' (black where there is none)."""
    i = int(index)
    if i < 0 or i >= len(rows) or not rows[i]: return np.zeros((ATLAS_WIDTH, 4))
    resolver.prefetch([rows[i]])
    c = next(e['Properties'] for e in json.load(open(resolver._file(rows[i]), encoding='utf-8')) if e.get('Type') == 'CurveLinearColor')
    chans = [(c.get(k) or {}).get('Keys', []) for k in ('FloatCurves', 'FloatCurves[1]', 'FloatCurves[2]', 'FloatCurves[3]')]
    t = np.arange(ATLAS_WIDTH) / (ATLAS_WIDTH - 1)
    out = np.zeros((ATLAS_WIDTH, 4))
    for ch, keys in enumerate(chans):
        out[:, ch] = [_eval(keys, x) for x in t] if keys else (1.0 if ch == 3 else 0.0)
    return out


def _write_curves(path, rows):
    a = np.stack(rows, 0)
    top = float(a[..., :3].max())
    if top > 1.0: print(f'  planets: {os.path.basename(path)} curves reach {top:.2f} (clipped to 1)')
    Image.fromarray(np.clip(np.round(a * 255), 0, 255).astype(np.uint8), 'RGBA').save(path)


# ---- the planets ------------------------------------------------------------------------------------------------------

def _srgb(resolver, path):
    """A texture's sRGB flag (its package's Texture2D export; Unreal's default: on)."""
    if not path: return False
    resolver.prefetch([path])
    try: d = json.load(open(resolver._file(path), encoding='utf-8'))
    except (OSError, ValueError): return False
    t = next((e for e in d if e.get('Type') == 'Texture2D'), None)
    return bool((t or {}).get('Properties', {}).get('SRGB', True))


def _values(p, names):
    return {n: round(float(p.scalars[n]), 6) for n in names if n in p.scalars}


def _colours(p, names):
    return {n: [round(float(x), 5) for x in p.vectors[n]] for n in names if n in p.vectors}


def spec(resolver, export, mod, key, surface, shell):
    """The planetSphere block of one planet (its files in <mod>/planets/)."""
    p = resolver.get(PLANETS + surface)
    cheap = 'M_Planet_SurfaceCheap' in p.chain
    rows = _atlas_rows(resolver)
    sw = lambda n, d=False: bool(p.switches.get(n, d))
    maps, wanted = {}, CHEAP_MAPS if cheap else SURFACE_MAPS
    if cheap and sw('Use Simple'): wanted = {'normal': 'Normal'}
    out = {'look': 'chorus', 'maps': maps}
    if cheap:
        out['chorus'] = {'kind': 'cheap', 'simple': sw('Use Simple'), 'values': {**_values(p, CHEAP_VALUES), **_colours(p, CHEAP_COLOURS)}}
    else:
        # (the master's defaults where an instance leaves a switch: as MI_Planet03c's compiled shader shows them)
        out['chorus'] = {'kind': 'surface', 'water': sw('Has Water'), 'clouds': sw('Has Clouds?', True),
                         'macroNormal': sw('Enable Macro Normalmap'), 'macroThreshold': sw('Macro As Height Treshold'),
                         'roughnessConstant': sw('Roughness | Use Constant', True), 'shadedSpecular': sw('Modify Shaded Specular'),
                         'values': {**_values(p, SURFACE_VALUES), **_colours(p, SURFACE_COLOURS)}}
        rel = f'planets/{key}_curves.png'
        _write_curves(os.path.join(mod, rel), [_curve_row(resolver, rows, p.scalar('Color | From Elevation')),
                                               _curve_row(resolver, rows, p.scalar('Atmosphere Color Directional')),
                                               _curve_row(resolver, rows, p.scalar('Atmosphere Color Fresnel'))])
        maps['curves'] = rel
    textures = {role: p.textures.get(param) for role, param in wanted.items() if p.textures.get(param)}
    if shell:
        s = resolver.get(PLANETS + shell)
        out['chorusAtmosphere'] = {'values': {**_values(s, SHELL_VALUES), **_colours(s, ['Overall Emissive Tint'])}}
        rel = f'planets/{key}_atmosphere_curves.png'
        _write_curves(os.path.join(mod, rel), [_curve_row(resolver, rows, s.scalar('Atmosphere Color Directional')),
                                               _curve_row(resolver, rows, s.scalar('Atmosphere Color Fresnel'))])
        maps['atmosphereCurves'] = rel
    resolver.fetch_textures([p.texture_paths.get(n) for n in textures.values()], export)
    srgb = [role for role, name in textures.items() if _srgb(resolver, p.texture_paths.get(name))]
    if srgb: out['chorus']['srgb'] = srgb
    for role, name in textures.items():
        src = os.path.join(export, (p.texture_paths.get(name) or '') + '.png')
        if not os.path.exists(src): print(f'  planet {key}: {name} not exported'); continue
        rel = f'planets/{name}.png'
        if not os.path.exists(os.path.join(mod, rel)): shutil.copyfile(src, os.path.join(mod, rel))
        maps[role] = rel
    return out


def build(export, mod, resolver, keys=None):
    """{key: planetSphere} for the regions' planets."""
    os.makedirs(os.path.join(mod, 'planets'), exist_ok=True)
    resolver.prefetch([PLANETS + m for _, s, sh in REGION_PLANETS for m in (s, sh) if m])
    out = {}
    for key, surface, shell in REGION_PLANETS:
        if keys and key not in keys: continue
        out[key] = spec(resolver, export, mod, key, surface, shell)
        c = out[key]['chorus']
        print(f"  planet {key}: {c['kind']}{' water' if c.get('water') else ''}{' clouds' if c.get('clouds') else ''}"
              f"{' + atmosphere' if 'chorusAtmosphere' in out[key] else ''}, {len(out[key]['maps'])} maps")
    return out
