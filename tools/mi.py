"""Chorus's material parameters as the game resolves them: a material instance's own values, then its parents' (each
instance names its parent), down to the master material's defaults. The exporter's per-mesh material JSON carries only
an instance's own overrides, so a value an instance inherits (the Elder Buddy's glow colour comes from
MI_Phoenix_outer_wing, four parents up) is read here.

    params = mi.Resolver(run, folder)       # run: import.py's exporter runner; folder: where the package dumps go
    params.prefetch([paths])                # one exporter run for many instances (and then their parents)
    p = params.get(path)                    # -> Params: .scalars, .vectors (linear rgb), .switches, .textures, .chain
"""
import json, os, re


def _find(o, key):
    if isinstance(o, dict):
        if key in o: return o[key]
        for v in o.values():
            r = _find(v, key)
            if r is not None: return r
    elif isinstance(o, list):
        for v in o:
            r = _find(v, key)
            if r is not None: return r
    return None


def _textures_in(o, out=None):
    """Every Texture2D an export references: [(name, pak path or None)]."""
    out = [] if out is None else out
    if isinstance(o, dict):
        n = o.get('ObjectName')
        if isinstance(n, str) and n.startswith("Texture2D'"):
            path = o.get('ObjectPath')
            out.append((n.split("'")[1], path.rsplit('.', 1)[0] if isinstance(path, str) else None))
        for v in o.values(): _textures_in(v, out)
    elif isinstance(o, list):
        for v in o: _textures_in(v, out)
    return out


def _rgb(c): return [round(float(c['R']), 4), round(float(c['G']), 4), round(float(c['B']), 4)]


class Params:
    def __init__(self):
        self.scalars, self.vectors, self.switches, self.textures, self.chain = {}, {}, {}, {}, []
        self.texture_paths = {}   # texture name -> its pak path (to export the ones an instance inherits)

    def scalar(self, name, default=0.0): return float(self.scalars.get(name, default))
    def vector(self, name, default=None): return self.vectors.get(name, default)
    def switch(self, name, default=False): return bool(self.switches.get(name, default))
    def texture(self, *names):
        for n in names:
            if self.textures.get(n): return self.textures[n]
        return None


class Resolver:
    def __init__(self, run, folder):
        self.run, self.folder = run, folder
        os.makedirs(folder, exist_ok=True)

    def _file(self, path): return os.path.join(self.folder, path.rsplit('/', 1)[-1] + '.json')

    def prefetch(self, paths):
        """Dumps the packages not dumped yet, then their parents, a generation per exporter run."""
        todo = [p for p in paths if not os.path.exists(self._file(p))]
        while todo:
            rx = '^(' + '|'.join(re.escape(p) for p in sorted(set(todo))) + r')\.uasset$'
            self.run('jsonall', rx, self.folder, capture=True)
            nxt = []
            for p in todo:
                if not os.path.exists(self._file(p)): continue   # (not in the pak: the chain stops there)
                par = self._parent(json.load(open(self._file(p), encoding='utf-8')))
                if par and not os.path.exists(self._file(par)): nxt.append(par)
            todo = nxt

    @staticmethod
    def _parent(d):
        par = _find(d, 'Parent')
        return par['ObjectPath'].rsplit('.', 1)[0] if isinstance(par, dict) and par.get('ObjectPath') else None

    def fetch_textures(self, paths, export):
        """Exports (as .png into export) the textures of these pak paths not exported yet: one exporter run."""
        todo = sorted({p for p in paths if p and not p.startswith('Engine/') and not os.path.exists(os.path.join(export, p + '.png'))})
        if not todo: return
        lst = os.path.join(self.folder, 'textures.txt')
        open(lst, 'w').write('\n'.join(todo) + '\n')
        self.run('export', lst, export, capture=True)

    def get(self, path):
        self.prefetch([path])
        p = Params()
        while path and os.path.exists(self._file(path)):
            d = json.load(open(self._file(path), encoding='utf-8'))
            p.chain.append(path.rsplit('/', 1)[-1])
            cached = _find(d, 'CachedExpressionData')
            if cached and _find(d, 'ScalarParameterValues') is None and _find(d, 'VectorParameterValues') is None:
                # the master material: its parameters' defaults (names and values in the same order)
                c = cached.get('Parameters', {})
                for a, b in zip(c.get('RuntimeEntries', {}).get('ParameterInfos', []), c.get('ScalarValues', [])):
                    p.scalars.setdefault(a['Name'], b)
                for a, b in zip(c.get('RuntimeEntries[1]', {}).get('ParameterInfos', []), c.get('VectorValues', [])):
                    p.vectors.setdefault(a['Name'], _rgb(b))
                # and the textures its graph samples without a parameter (M_TG_Atlas_0x's own maps), as 'ref:<name>'
                for t in _textures_in(d):
                    p.textures.setdefault('ref:' + t[0], t[0])
                    if t[1]: p.texture_paths.setdefault(t[0], t[1])
                for a, b in zip(c.get('RuntimeEntries[2]', {}).get('ParameterInfos', []), c.get('TextureValues', [])):
                    if isinstance(b, dict) and b.get('ObjectName'):
                        name = b['ObjectName'].split("'")[1]
                        p.textures.setdefault(a['Name'], name)
                        if b.get('ObjectPath'): p.texture_paths.setdefault(name, b['ObjectPath'].rsplit('.', 1)[0])
                break
            for x in _find(d, 'ScalarParameterValues') or []: p.scalars.setdefault(x['ParameterInfo']['Name'], x['ParameterValue'])
            for x in _find(d, 'VectorParameterValues') or []: p.vectors.setdefault(x['ParameterInfo']['Name'], _rgb(x['ParameterValue']))
            for x in _find(d, 'TextureParameterValues') or []:
                v = x['ParameterValue']
                if not isinstance(v, dict) or not v.get('ObjectName'): continue
                name = v['ObjectName'].split("'")[1]
                p.textures.setdefault(x['ParameterInfo']['Name'], name)
                if v.get('ObjectPath'): p.texture_paths.setdefault(name, v['ObjectPath'].rsplit('.', 1)[0])
            for x in (_find(d, 'StaticParameters') or {}).get('StaticSwitchParameters', []):
                p.switches.setdefault(x['ParameterInfo']['Name'], x['Value'])
            path = self._parent(d)
        return p
