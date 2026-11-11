"""The conversions the importer relies on, on synthetic data (no game files): Unreal's export frame -> the remake's
mounts, Chorus's RMO / normal / emissive maps -> URP's, the nozzle finder, and the glb round trip."""
from pathlib import Path
import sys, tempfile, os, unittest, json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import ships, textures, glb, sounds, weapons, mi, npcs


class MountTests(unittest.TestCase):
    def test_axes(self):
        k = ships.K
        self.assertEqual([0.0, 0.0, round(k, 1)], ships.to_game([1, 0, 0]))     # glTF +X (the nose) -> game +z
        self.assertEqual([0.0, round(k, 1), 0.0], ships.to_game([0, 1, 0]))     # up stays up
        self.assertEqual([round(-k, 1), 0.0, 0.0], ships.to_game([0, 0, 1]))    # glTF +Z (Unreal's right) -> game -x (x is the pilot's left)

    def test_scale(self):
        self.assertAlmostEqual(72.0, ships.K)   # 3.6x Chorus size, 0.05 m per game unit


class MapTests(unittest.TestCase):
    def test_rmo(self):
        rmo = np.array([[[0.25, 0.8, 0.5, 1.0]]], np.float32)
        ms = textures.convert_rmo(rmo)
        self.assertAlmostEqual(0.8, ms[0, 0, 0]); self.assertAlmostEqual(0.75, ms[0, 0, 3])

    def test_normal_green_flipped(self):
        n = np.array([[[0.5, 0.2, 1.0, 1.0]]], np.float32)
        self.assertAlmostEqual(0.8, textures.flip_normal(n)[0, 0, 1])

    def test_emission_masks(self):
        e = np.zeros((2, 2, 4), np.float32); e[0, 0, 1] = 1.0; e[1, 1, 2] = 1.0
        m, peak = textures.emission(e, [(1, [1, 0, 0], 2.0), (2, [0, 0, 1], 0.0)])
        self.assertAlmostEqual(2.0, peak)
        self.assertAlmostEqual(1.0, float(m[0, 0, 0]), places=3)
        self.assertEqual(0.0, float(m[1, 1].max()), 'a multiplier of 0 lights nothing')
        self.assertIsNone(textures.emission(e, [(1, [1, 1, 1], 0.0)]))


def _box(x0, x1, z0, z1):
    """A box's 12 triangles, outward normals (counter-clockwise)."""
    v = np.array([[x, y, z] for x in (x0, x1) for y in (-0.5, 0.5) for z in (z0, z1)], np.float32)
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return v, np.array(faces, np.uint32).reshape(-1)


class NozzleTests(unittest.TestCase):
    def test_rear_faces_per_side(self):
        v1, i1 = _box(-2.0, 1.0, 1.0, 3.0); v2, i2 = _box(-2.0, 1.0, -3.0, -1.0)
        prims = [('T', {'POSITION': np.vstack([v1, v2])}, np.concatenate([i1, i2 + len(v1)]))]
        found = ships.nozzle_faces(prims, 'T')
        self.assertEqual(2, len(found))
        for c, (hh, hw) in found:
            self.assertAlmostEqual(-2.0, c[0], places=4)   # the rear face
            self.assertAlmostEqual(2.0, abs(c[2]), places=1)


class GlbTests(unittest.TestCase):
    def test_round_trip(self):
        v, i = _box(-1, 1, -1, 1)
        attrs = {'POSITION': v, 'NORMAL': np.tile([0, 1, 0], (len(v), 1)).astype(np.float32), 'TEXCOORD_0': np.zeros((len(v), 2), np.float32)}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.glb')
            glb.save(p, [('MatA', attrs, i)])
            back = glb.static_mesh(p)
            self.assertEqual('MatA', back[0][0])
            np.testing.assert_allclose(v, back[0][1]['POSITION'])
            np.testing.assert_array_equal(i, back[0][2])


class SoundTests(unittest.TestCase):
    def test_loudness_loop_and_shot(self):
        rate = 48000
        t = np.arange(rate) / rate
        loop = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)[:, None]
        self.assertAlmostEqual(0.5 / np.sqrt(2), sounds.loudness(loop, rate, True), places=3)   # a loop: its RMS
        shot = np.zeros((rate, 2), np.float32)
        shot[1000:1000 + rate // 10] = 0.8   # a loud 100 ms in a second of silence
        self.assertAlmostEqual(0.8, sounds.loudness(shot, rate, False), places=3)   # a shot: its loudest 60 ms

    def test_every_ship_sound_is_a_known_slot(self):
        slots = {'engine', 'boostStart', 'boostLoop', 'boostStop', 'driftStart', 'driftLoop', 'driftStop', 'dodge',
                 'travelStart', 'travelLoop', 'travelStop'}
        self.assertEqual(slots, set(sounds.SHIP))


class KitTests(unittest.TestCase):
    def test_a_weapon_glb_has_its_muzzle_at_the_front(self):
        from tools import kit
        v, i = _box(-1.0, 2.0, -0.5, 0.5)
        prims = [('MatA', {'POSITION': v}, i)]
        m = kit.muzzle(prims)
        self.assertAlmostEqual(2.0, m[0]); self.assertAlmostEqual(0.0, m[1]); self.assertAlmostEqual(0.0, m[2])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'w.glb')
            glb.save(p, prims, 'gun', nodes={'muzzle': m})
            np.testing.assert_allclose([2.0, 0.0, 0.0], glb.joint_positions(p)['muzzle'], atol=1e-6)

    def test_the_kit_ship_keeps_the_ship_but_its_model(self):
        from tools import kit
        ship = {'id': 'forsaken', 'model': 'models/forsaken.glb', 'modelLength': 749, 'modelYaw': 90, 'hangarHeight': 107,
                'materials': [{'material': 'M'}], 'mounts': [{'slotType': 0}], 'armor': 560}
        elder = dict(ship, id='elder_buddy', name='Elder Buddy', engineGlowColor=[1, 0.4, 0],
                     materials=[{'material': 'M', 'diffuse': 'maps/e_c.png', 'engine': True}])
        with tempfile.TemporaryDirectory() as d:
            kits, entries = kit.build(d, d, ship, skinned=[elder])   # no export: no weapon models, the defaults only
        entry = entries[0]
        self.assertEqual('forsaken', entry['kit']); self.assertNotIn('model', entry); self.assertEqual(560, entry['armor'])
        self.assertEqual(ship['mounts'], entry['mounts'])
        k = kits[0]
        self.assertEqual((3.6, 90), (k['scale'], k['yaw']))
        self.assertEqual('models/forsaken.glb', k['parts'][0]['model'])
        self.assertEqual([{'slot': 'secondary', 'model': ''}], k['hardpoints']['weapons'])
        # the Elder Buddy: a skin of the kit (maps only) and a ship that wears it
        self.assertEqual({'hull': 'forsaken', 'skin': 'elder_buddy'}, entries[1]['build'])
        self.assertEqual([{'material': 'M', 'diffuse': 'maps/e_c.png'}], k['skins'][0]['materials'])
        self.assertEqual([1, 0.4, 0], k['skins'][0]['engineColor'])


class WeaponTests(unittest.TestCase):
    def test_names_come_from_the_master_data(self):
        master = [{'Properties': {'WeaponsMasterData': [{'ItemName': 'Gatling_T1', 'ItemDisplayName': {'LocalizedString': 'BIG  GUN'},
                   'ItemDescription': {'LocalizedString': 'It shoots.'},
                   'PerkDescription0': {'LocalizedString': 'FAST - Shoots fast.'}}]}}]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm.json'); json.dump(master, open(p, 'w'))
            items = weapons.build('', d, p)
        t1 = next(i for i in items if i['id'] == 'chorus_gatling_t1')
        self.assertEqual('Big Gun', t1['name'])
        self.assertEqual('It shoots. Shoots fast. (Chorus)', t1['description'])

    def test_items_without_an_export_keep_their_base_sounds(self):
        with tempfile.TemporaryDirectory() as d:
            items = weapons.build('', d)
        self.assertEqual(15, len(items))
        ids = {i['id']: i for i in items}
        self.assertEqual(15, len(ids), 'unique ids')
        self.assertEqual([27, 8, 37], [ids[k]['base'] for k in ('chorus_gatling_t1', 'chorus_laser_t1', 'chorus_missiles_t1')])
        for i in items:
            self.assertNotIn('shot', i.get('fx', {}))
            self.assertIn(i['techLevel'], (7, 8, 9))
        gat, laser = ids['chorus_gatling_t1']['stats'], ids['chorus_laser_t1']['stats']
        ratio = (laser['damage'] / laser['loadingTimeMs']) / (gat['damage'] / gat['loadingTimeMs'])
        self.assertAlmostEqual(83 / 133, ratio, delta=0.02)   # Chorus's laser rifle / gatling per second


class MaterialTests(unittest.TestCase):
    def test_tangent_handedness_follows_the_uvs(self):
        # a quad facing +z, u along +x and v down the image (-y): glTF's bitangent (+Y, up the normal map) is +y -> w = +1;
        # the same quad with its u mirrored -> w = -1
        pos = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
        nrm = np.tile([0, 0, 1], (4, 1)).astype(np.float32)
        idx = np.array([0, 1, 2, 0, 2, 3], np.uint32)
        uv = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], np.float32)
        tan = np.tile([1, 0, 0, 1], (4, 1)).astype(np.float32)
        np.testing.assert_array_equal([1, 1, 1, 1], glb.tangent_signs(pos, nrm, tan, uv, idx)[:, 3])
        mirrored = uv * [-1, 1] + [1, 0]
        tan_m = np.tile([-1, 0, 0, 1], (4, 1)).astype(np.float32)
        np.testing.assert_array_equal([-1, -1, -1, -1], glb.tangent_signs(pos, nrm, tan_m, mirrored, idx)[:, 3])

    def test_vertex_colours_bake_over_the_uvs(self):
        uv = np.array([[0, 0], [1, 0], [0, 1]], np.float32)
        col = np.array([[1, 0, 0], [1, 0, 0], [1, 0, 0]], np.float32)
        img = textures.bake_vertex_colours(uv, col, np.array([0, 1, 2]), 16)
        np.testing.assert_allclose([1, 0, 0], img[2, 2], atol=1e-5)   # inside the triangle
        self.assertEqual((16, 16, 3), img.shape)

    def test_parameters_come_through_the_parents(self):
        def inst(parent, **kw):
            d = {'Parent': {'ObjectPath': parent + '.0'} if parent else None}
            d.update(kw); return [{'Properties': d}]
        with tempfile.TemporaryDirectory() as d:
            files = {'MI_Child': inst('P/MI_Parent', ScalarParameterValues=[{'ParameterInfo': {'Name': 'Emissive02_Multiplier'}, 'ParameterValue': 2.0}]),
                     'MI_Parent': inst('P/M_Master', VectorParameterValues=[{'ParameterInfo': {'Name': 'Emissive02'}, 'ParameterValue': {'R': 0.2, 'G': 1, 'B': 0.8}}]),
                     'M_Master': [{'CachedExpressionData': {'Parameters': {
                         'RuntimeEntries': {'ParameterInfos': [{'Name': 'Emissive02_Multiplier'}, {'Name': 'Emissive03_Multiplier'}]},
                         'RuntimeEntries[1]': {'ParameterInfos': [{'Name': 'Emissive02'}, {'Name': 'Emissive03'}]},
                         'ScalarValues': [1.0, 0.0], 'VectorValues': [{'R': 0, 'G': 1, 'B': 0}, {'R': 0, 'G': 0, 'B': 1}]}}}]}
            for n, v in files.items(): json.dump(v, open(os.path.join(d, n + '.json'), 'w'))
            p = mi.Resolver(lambda *a, **k: None, d).get('P/MI_Child')
        self.assertEqual(['MI_Child', 'MI_Parent', 'M_Master'], p.chain)
        self.assertEqual(2.0, p.scalar('Emissive02_Multiplier'))
        self.assertEqual([0.2, 1.0, 0.8], p.vector('Emissive02'))      # the parent's, not the master's default
        self.assertEqual([0.0, 0.0, 1.0], p.vector('Emissive03'))      # the master's default
        # Emissive03's multiplier is 0: only green (Emissive02) glows
        self.assertEqual([(1, [0.2, 1.0, 0.8], 2.0)], [c for c in ships._colours(p) if c[0] != 0])

    def test_a_hull_is_turned_nose_forward(self):
        v = np.array([[0, 0, 5], [0, 0, -5], [1, 0, 0]], np.float32)
        prims = [('Hull', {'POSITION': v}, np.array([0, 1, 2])), ('MI_Thruster', {'POSITION': np.array([[0.5, 0, -5]], np.float32)}, np.array([0]))]
        self.assertEqual('+z', npcs._nose(prims))                       # away from the thruster
        turned = npcs._turn(prims, '+z')[0][1]['POSITION']
        np.testing.assert_allclose([5, 0, 0], turned[0])                # the nose now at +X


if __name__ == '__main__':
    unittest.main()
