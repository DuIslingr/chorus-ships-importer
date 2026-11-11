"""Chorus's skies (ArtAssets/Environment/Skyboxes: one material instance of M_Skybox_MASTER per region) as the remake's
systems.json "skybox": the sky drawn live by Chorus's own formula (its "chorus" block, GoF2/SpaceSky's ChorusSky; Options >
Graphics "Live mod skies") and, for Low and for the crossfade between systems, the same formula baked into a 2:1 panorama
(its "nebula"). Modding/README "Chorus skies".

M_Skybox_MASTER, from its compiled pixel shader (MI_Skybox_LocRSA's, and the variants with a fourth layer and without the
gradient; the material's preshader gives each constant's parameter):

    colour = gradient: (dot(n, up) + bias)^gamma, ColorA -> ColorB by that (clamped to 1), times it, times Gradient Opacity
             (n: the sky sphere's inward normal, Unreal's axes; static switch "Add Skybox Gradient")
           + stars: the star mask (StarsAtlas, linear, its red) at the sky sphere's UV + offset, times tiling, through the
             CA_Skybox row Stars_Curve (C_Skybox_Stars: 0 at 0.182, 1 at 0.536 in each of r, g, b), ^Stars_Exponent,
             x Stars_Brightness, its r + g + b (the sphere's vertex colours: none, so white)
    then each layer on (static switches Layer1..Layer4), in order: the direction turned by its heading (x 2 pi) and
             elevation (x -pi / 2), to a lon-lat UV, centred and scaled by Scale (u by Scale / 2), turned by Rotation
             (x 2 pi); its image there (sRGB), colour = rgb + (rgb x Emissive)^exponent, laid over by alpha x Opacity
             inside the image's square. The exponent: layers 1 and 2 both read Layer2_EmissiveExponent (as Chorus does),
             3 and 4 their own.
    x OverallEmissive (its exposure compensation cancels Chorus's auto exposure, which the remake hasn't).

The sky sphere (BP_SkySphere: SM_Sphere, a 16 x 16 UV sphere about Unreal's y) maps the stars by u = 0.75 - atan2(z, x) /
2 pi (wrapped at the seam), v = 0.5 + asin(y) / pi. The same in SpaceSkyCore.hlsl; keep the two in step.
"""
import json, math, os, shutil
import numpy as np
from PIL import Image

UP = 'SpacePrototype/Content/UnleashedPrototype/'
SKYBOXES = UP + 'ArtAssets/Environment/Skyboxes/'
CURVE_ATLAS = UP + 'MaterialLibrary/Skybox/CA_Skybox'
# (key, material instance): the regions' skies (Maps.locres: RSA / RSB Stega, TRN Amarok, ASP / AST Nimika, MIF / LAB Tarris)
SKIES = [('stega', 'MI_Skybox_LocRSA'), ('stega_b', 'MI_Skybox_LocRSB'), ('amarok', 'MI_Skybox_LocTRN_02'),
         ('nimika', 'MI_Skybox_LocASP'), ('nimika_b', 'MI_Skybox_LocAST'), ('tarris', 'MI_Skybox_LocMIF'),
         ('tarris_b', 'MI_Skybox_LocLAB_Alt')]
# a layer of a planet's atmosphere glow (T_LocASP_Atmosphere: red and blue sectors round a centre the region's big planet
# covers in Chorus): left out, as the sky has no planet in front of it (the planets bring their own glow)
SKIP_LAYERS = ('Atmosphere',)
PANORAMA = (4096, 2048)   # the bake: Low's sky and the crossfade's (the live shader is sharp at any size)
SUPERSAMPLE = 2


def _s(p, name, default=0.0): return float(p.scalars.get(name, default))


def _curve(resolver, row):
    """The CA_Skybox row's curve as two keys [[time, r, g, b], [time, r, g, b]] (its curves are two linear keys each)."""
    resolver.prefetch([CURVE_ATLAS])
    atlas = json.load(open(resolver._file(CURVE_ATLAS), encoding='utf-8'))
    curves = next(e['Properties']['GradientCurves'] for e in atlas if e.get('Type') == 'CurveLinearColorAtlas')
    path = curves[min(int(row), len(curves) - 1)]['ObjectPath'].rsplit('.', 1)[0]
    resolver.prefetch([path])
    c = next(e['Properties'] for e in json.load(open(resolver._file(path), encoding='utf-8')) if e.get('Type') == 'CurveLinearColor')
    chans = [c[k]['Keys'] for k in ('FloatCurves', 'FloatCurves[1]', 'FloatCurves[2]')]
    if any(len(k) != 2 or k[0]['Time'] != chans[0][0]['Time'] or k[1]['Time'] != chans[0][1]['Time'] for k in chans):
        print(f'  sky: the star curve {path} is not two shared linear keys; using its first and last')
    return [[round(chans[0][i]['Time'], 5)] + [round(k[min(i, len(k) - 1) if i == 0 else -1]['Value'], 5) for k in chans] for i in (0, 1)]


def block(resolver, mi_name):
    """The skybox's "chorus" block (its images as pak texture names, swapped for the mod's paths by build)."""
    p = resolver.get(SKYBOXES + mi_name)
    sw = lambda n, d=False: bool(p.switches.get(n, d))
    out = {'emissive': round(_s(p, 'OverallEmissive', 1.0), 4)}
    if sw('Add Skybox Gradient'):
        out['gradient'] = {'up': p.vector('SkyboxGradient_UpVector', [0, 0, 1]), 'bias': round(_s(p, 'SkyboxGradient_Bias'), 4),
                           'gamma': round(_s(p, 'SkyboxGradient_Gamma', 1.0), 4), 'opacity': round(_s(p, 'Gradient Opacity', 1.0), 4),
                           'colorA': p.vector('SkyboxGradient_ColorA', [0, 0, 0]), 'colorB': p.vector('SkyboxGradient_ColorB', [0, 0, 0])}
    out['stars'] = {'image': p.textures.get('StarsAtlas'), 'tiling': round(_s(p, 'Stars_Tiling', 1.0), 4),
                    'offset': [round(_s(p, 'Stars Offset U'), 4), round(_s(p, 'Stars Offset V'), 4)],
                    'brightness': round(_s(p, 'Stars_Brightness', 1.0), 4), 'exponent': round(_s(p, 'Stars_Exponent', 1.0), 4),
                    'curve': _curve(resolver, _s(p, 'Stars_Curve', 3.0))}
    layers = []
    for n in (1, 2, 3, 4):
        if not sw(f'Layer{n}'): continue
        if any(k in (p.textures.get(f'Layer{n}_Nebula') or '') for k in SKIP_LAYERS): continue
        exp = 'Layer2_EmissiveExponent' if n <= 2 else f'Layer{n}_EmissiveExponent'
        layers.append({'image': p.textures.get(f'Layer{n}_Nebula'), 'heading': round(_s(p, f'Layer{n}_Heading'), 4),
                       'elevation': round(_s(p, f'Layer{n}_Elevation'), 4), 'scale': round(_s(p, f'Layer{n}_Scale', 1.0), 4),
                       'rotation': round(_s(p, f'Layer{n}_Rotation'), 4), 'emissive': round(_s(p, f'Layer{n}_Emissive', 1.0), 4),
                       'exponent': round(_s(p, exp, 2.0), 4), 'opacity': round(_s(p, f'Layer{n}_Opacity', 1.0), 4)})
    out['layers'] = layers
    return out, p


# ---- the formula in numpy (SpaceSkyCore.hlsl's ChorusSky) ---------------------------------------------------------------

def _srgb_to_linear(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def _linear_to_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def _sample(img, u, v):
    """Bilinear, wrapping, at Unity's texture coordinates (v up; img rows top first)."""
    h, w = img.shape[:2]
    x = u * w - 0.5; y = (1.0 - v) * h - 0.5
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def _pow0(x, e): return np.where(x > 1e-6, np.power(np.maximum(x, 1e-6), e), 0.0)


def shade(c, images, w):
    """The sky toward Unity directions w (n x 3, sky space): linear rgb (n x 3)."""
    v = np.stack([w[:, 2], w[:, 0], w[:, 1]], 1)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    d = -v
    col = np.zeros_like(v)
    g = c.get('gradient')
    if g:
        up = np.asarray(g['up'], np.float64); up = up / max(np.linalg.norm(up), 1e-12)
        t = d @ up + g['bias']
        t = np.where(t <= 0, 0.0, np.power(np.maximum(t, 1e-12), g['gamma']))
        a, b = np.asarray(g['colorA']), np.asarray(g['colorB'])
        col = (a + (b - a) * np.minimum(t, 1)[:, None]) * t[:, None] * g['opacity']
    s = c['stars']
    u = np.mod(0.75 - np.arctan2(v[:, 2], v[:, 0]) / (2 * math.pi), 1.0)
    vv = 0.5 + np.arcsin(np.clip(v[:, 1], -1, 1)) / math.pi
    su = (u + s['offset'][0]) * s['tiling']; sv = (vv + s['offset'][1]) * s['tiling']
    m = _sample(images[s['image']], su, 1.0 - sv)[:, 0] if s.get('image') in images else np.zeros(len(v))
    (t0, *c0), (t1, *c1) = s['curve']
    k = np.clip((m - t0) / max(t1 - t0, 1e-5), 0, 1)[:, None]
    curve = np.asarray(c0) + (np.asarray(c1) - np.asarray(c0)) * k
    col = col + (_pow0(curve, s['exponent']) * s['brightness']).sum(1, keepdims=True)
    for l in c['layers']:
        if l['image'] not in images: continue
        h = l['heading'] * 2 * math.pi; e = -l['elevation'] * 0.5 * math.pi; r = l['rotation'] * 2 * math.pi
        sh, ch, se, ce = math.sin(h), math.cos(h), math.sin(e), math.cos(e)
        p = np.stack([d[:, 1] * sh + d[:, 2] * ch, d[:, 0], d[:, 1] * ch - d[:, 2] * sh], 1)
        q = np.stack([p[:, 2], p[:, 0] * ce - p[:, 1] * se, p[:, 0] * se + p[:, 1] * ce], 1)
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        lu = (np.arctan2(q[:, 0], -q[:, 1]) / math.pi + 1) * 0.5
        lv = np.arccos(np.clip(q[:, 2], -1, 1)) / math.pi
        sc = l['scale'] if abs(l['scale']) > 1e-4 else 1e-4
        kx, ky = (2 * lu - 1) / sc, (lv - 0.5) / sc
        rx, ry = kx * math.cos(r) - ky * math.sin(r), kx * math.sin(r) + ky * math.cos(r)
        t = _sample(images[l['image']], rx + 0.5, 0.5 + ry)
        rgb = t[:, :3] + _pow0(t[:, :3] * l['emissive'], l['exponent'])
        inside = ((np.abs(rx) < 0.5) & (np.abs(ry) < 0.5)).astype(np.float64)
        a = (t[:, 3] * l['opacity'] * inside)[:, None]
        col = col + (rgb - col) * a
    return np.maximum(col, 0) * c['emissive']


def bake(c, images, size=PANORAMA, ss=SUPERSAMPLE):
    """The 2:1 panorama of the sky (GoF2/SpaceSky's PanoramaUV: middle +Z, top +Y): linear rgb, rows top first."""
    W, H = size
    out = np.zeros((H, W, 3), np.float32)
    rows = 64
    for y0 in range(0, H, rows):
        y1 = min(H, y0 + rows)
        acc = np.zeros((y1 - y0, W, 3))
        for sy in range(ss):
            for sx in range(ss):
                jj, ii = np.meshgrid((np.arange(W) + (sx + 0.5) / ss) / W, (np.arange(y0, y1) + (sy + 0.5) / ss) / H)
                lon = (jj - 0.5) * 2 * math.pi; lat = (0.5 - ii) * math.pi
                w = np.stack([np.sin(lon) * np.cos(lat), np.sin(lat), np.cos(lon) * np.cos(lat)], -1).reshape(-1, 3)
                acc += shade(c, images, w).reshape(y1 - y0, W, 3)
        out[y0:y1] = acc / (ss * ss)
    return out


# ---- the mod's files ---------------------------------------------------------------------------------------------------

BAKE_TEXTURE = 2048   # the images' size for the bake (the panorama is 4096 wide: a layer's square spans at most half of it)


def _load(path, linear):
    im = Image.open(path).convert('RGBA')
    if max(im.size) > BAKE_TEXTURE: im = im.resize((min(im.width, BAKE_TEXTURE), min(im.height, BAKE_TEXTURE)), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255.0
    if not linear: a[..., :3] = _srgb_to_linear(a[..., :3])
    return a


def build(export, mod, resolver, keys=None):
    """{key: systems.json "skybox"} for the regions' skies; their images in <mod>/skies/."""
    os.makedirs(os.path.join(mod, 'skies'), exist_ok=True)
    blocks = {}
    for key, mi_name in SKIES:
        if keys and key not in keys: continue
        blocks[key] = block(resolver, mi_name)
    resolver.fetch_textures([p.texture_paths.get(n) for b, p in blocks.values()
                             for n in [b['stars']['image']] + [l['image'] for l in b['layers']]], export)
    out, copied, cache = {}, {}, {}
    for key, (b, p) in blocks.items():
        images = {}
        def place(name, star):
            src = os.path.join(export, (p.texture_paths.get(name) or '') + '.png')
            if not name or not os.path.exists(src): print(f'  sky {key}: {name} not exported'); return None
            if name not in cache: cache[name] = _load(src, linear=star)
            images[name] = cache[name]
            rel = f'skies/{name}.png'
            if rel not in copied:
                if star:   # the mask is linear: stored sRGB-encoded, so the remake's sRGB sampling gives Chorus's values back
                    m = np.asarray(Image.open(src).convert('RGBA'), np.float32)[..., 0] / 255.0
                    enc = np.clip(np.round(_linear_to_srgb(m) * 255), 0, 255).astype(np.uint8)
                    Image.fromarray(np.stack([enc, enc, enc], -1), 'RGB').save(os.path.join(mod, rel), optimize=True)
                else: shutil.copyfile(src, os.path.join(mod, rel))
                copied[rel] = True
            return rel
        live = json.loads(json.dumps(b))
        live['stars']['image'] = place(b['stars']['image'], True)
        for l, ll in zip(b['layers'], live['layers']): ll['image'] = place(l['image'], False)
        live['layers'] = [l for l in live['layers'] if l['image']]
        if not live['stars']['image']: del live['stars']['image']
        print(f'  sky {key}: baking {PANORAMA[0]} x {PANORAMA[1]}...')
        pano = bake(b, images)
        # the panorama is a PNG (8 bits, sRGB): its brightest stays bright through "nebulaBrightness" (the brightest 1 %:
        # the stars, white either way, clip; scaled by them, a sky of Stars_Brightness 100 came out black)
        top = float(np.percentile(pano.max(-1), 99.0))
        gain = max(1.0, top)
        enc = np.clip(np.round(_linear_to_srgb(pano / gain) * 255), 0, 255).astype(np.uint8)
        rel = f'skies/{key}.png'
        Image.fromarray(enc, 'RGB').save(os.path.join(mod, rel), optimize=True)
        out[key] = {'nebula': rel, 'stars': 'none', 'nebulaBrightness': round(gain, 4), 'chorus': live}
    return out
