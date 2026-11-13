"""The conversions the importer relies on, on synthetic data (no game files): Unreal's export frame -> the remake's
mounts, Chorus's RMO / normal / emissive maps -> URP's, the nozzle finder, and the glb round trip."""
from pathlib import Path
import sys, tempfile, os, unittest, json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import ships, textures, glb, sounds, weapons, mi, npcs, rig


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

    def test_station_lights_pick_their_channel_by_uv1_quadrant(self):
        from tools import npcs
        class P:   # (four channels; strength 1)
            def vector(self, k): return {'Emissive_01_Color': [1, 0, 0], 'Emissive_02_Color': [0, 1, 0], 'Emissive_03_Color': [0, 0, 1], 'Emissive_04_Color': [1, 1, 1]}.get(k)
            def scalar(self, k, d=0.0): return 1.0
        uv = np.array([[.2, .2], [.3, .2], [.2, .3], [.8, .2], [.9, .2], [.8, .3], [.2, .8], [.3, .8], [.2, .9], [.8, .8], [.9, .8], [.8, .9]], np.float32)
        got = {tag: col for tag, col, _ in npcs._station_lights(P(), {'TEXCOORD_1': uv}, np.arange(12, dtype=np.uint32))}
        self.assertEqual({'q00': [1, 0, 0], 'q10': [0, 1, 0], 'q01': [0, 0, 1], 'q11': [1, 1, 1]}, got)

    def test_palette_metal_is_layer_data_blue(self):
        from tools import npcs
        self.assertEqual(2, npcs.DATA_METAL)   # (the Prophet's white swatches black in its dim arena: metal)

    def test_trim_bake_follows_the_compiled_shader(self):
        # TRIM_SHADER: metallic = saturate((LayerData.b - .5) x 2 + Tiling RMO.g), roughness = lerp(LayerData.r,
        # LayerData.g, Tiling RMO.r), occlusion = Tiling RMO.b x Trim AAO.b; the tiling layer over UV set 1
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            def png(name, rgb):
                p = os.path.join(d, name + '.png'); Image.new('RGB', (4, 4), rgb).save(p); return p
            r = {'kind': 'trim', 'colors': png('c', (255, 255, 255)), 'data': png('d', (51, 153, 255)),
                 'trmo': png('t', (128, 0, 255)), 'tdiff': png('f', (255, 255, 255)), 'aro': png('a', (0, 0, 255)), 'tile': 2.0}
            attrs = {'POSITION': np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], np.float32), 'NORMAL': np.tile([0, 0, 1], (3, 1)).astype(np.float32)}
            for k in range(4): attrs[f'TEXCOORD_{k}'] = np.array([[0.05, 0.05], [0.95, 0.05], [0.05, 0.95]], np.float32)
            _, ms, _, _ = npcs.bake_hull([(attrs, np.array([0, 1, 2], np.uint32), r)], 16)
            npcs._IMG.clear()
        np.testing.assert_allclose([1.0, 1.0 - (0.2 + 0.4 * 128 / 255)], ms[3, 3, [0, 3]], atol=0.01)
        np.testing.assert_allclose([0.0], npcs._data_metal(np.array([[0, 0, 126 / 255]])), atol=1e-6)   # (a half-blue swatch: paint)

    def test_chorus_palette_is_linear_colours_beside_the_data(self):
        # the remake's ChorusLayers reads the left half as linear colour and the right half as LayerData, by texel
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            c = os.path.join(d, 'T_X_Colors.png'); Image.new('RGB', (4, 4), (188, 188, 188)).save(c)
            dd = os.path.join(d, 'T_X_Data.png'); Image.new('RGB', (4, 4), (10, 20, 255)).save(dd)
            rel = npcs._chorus_palette(d, c, dd)
            a = np.asarray(Image.open(os.path.join(d, rel)).convert('RGB'))
        self.assertEqual((4, 8, 3), a.shape)
        self.assertAlmostEqual(0.5, a[0, 0, 0] / 255, delta=0.01)          # (sRGB 188 is linear 0.5)
        np.testing.assert_array_equal([10, 20, 255], a[0, 4])

    def test_chorus_hulls_share_one_vertex_layout(self):
        # glTFast reads one layout per mesh: every primitive gets UV sets 0 - 3 and vertex colours
        n = 3
        plain = {'POSITION': np.zeros((n, 3), np.float32), 'NORMAL': np.zeros((n, 3), np.float32), 'TEXCOORD_0': np.zeros((n, 2), np.float32)}
        out = npcs._uniform([('glow', plain, np.arange(3, dtype=np.uint32))])
        self.assertEqual(set(npcs.CHORUS_KEEP), set(out[0][1]))
        np.testing.assert_array_equal(np.ones((n, 4)), out[0][1]['COLOR_0'])   # (white where a part has none)

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


class RigTests(unittest.TestCase):
    def test_unreal_bone_poses_become_the_exports_node_poses(self):
        # measured on the Forsaken's skeleton: Unreal (cm, x y z, quaternion x y z w) against the exported node
        ue = [-145.5, -36.36, -1.3, -0.27, 0.0, 0.0, -0.9629, 1, 1, 1]
        np.testing.assert_allclose([-1.455, -0.013, -0.3636], rig._ue_t(ue), atol=1e-4)
        np.testing.assert_allclose([-0.27, 0.0, 0.0, 0.9629], rig._ue_q(ue), atol=1e-4)
        ue2 = [-20.2, -152.68, -39.73, 0.0, -0.0, 0.3341, -0.9425, 1, 1, 1]
        np.testing.assert_allclose([0.0, 0.3341, 0.0, 0.9425], rig._ue_q(ue2), atol=1e-4)

    def test_every_clip_keys_every_moving_part_and_idle_holds_the_rest_pose(self):
        nodes = [{'name': 'BONE_a', 'translation': [0, 0, 0], 'rotation': [0, 0, 0, 1]},
                 {'name': 'BONE_b', 'translation': [1, 0, 0], 'rotation': [0, 0, 0, 1]}]
        still = [100, 0, 0, 0, 0, 0, 1, 1, 1, 1]                     # BONE_b at rest (1 m along x)
        moved = [[100, 0, 0, 0, 0, 0, 1, 1, 1, 1], [100, 0, 50, 0, 0, 0, 1, 1, 1, 1]]   # up 0.5 m (Unreal z -> glTF y)
        anims = {'idle': None, 'open': {'fps': 2, 'frames': 2, 'bones': {'BONE_a': [[0] * 6 + [1, 1, 1, 1]] * 2, 'BONE_b': moved}}}
        out = dict(rig.clips(anims, nodes))
        self.assertEqual({(1, 'translation'), (1, 'rotation')}, {(n, p) for n, p, _, _ in out['idle']})   # only the moving part
        idle_t = next(v for n, p, t, v in out['idle'] if p == 'translation')
        np.testing.assert_allclose([[1, 0, 0], [1, 0, 0]], idle_t)
        open_t, open_v = next((t, v) for n, p, t, v in out['open'] if p == 'translation')
        np.testing.assert_allclose([0.0, 0.5], open_t)
        np.testing.assert_allclose([1, 0.5, 0], open_v[1])


class RiteTests(unittest.TestCase):
    def test_the_hunt_is_a_rite_device_with_its_icon_on_a_plate(self):
        from PIL import Image
        from tools import rites
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, 'export', rites.ICONS + 'T_Powers_Power2_Icn.png')
            src.parent.mkdir(parents=True)
            Image.new('RGBA', (264, 264), (255, 255, 255, 255)).save(src)
            out = Path(tmp, 'mod')
            items = rites.items(str(Path(tmp, 'export')), str(out))
            hunt = next(i for i in items if i['id'] == 'chorus_rite_hunt')
            self.assertEqual({'cabinSize': 0, 'device': 23, 'deviceRiteCost': 2, 'deviceCooldownMs': 500}, hunt['stats'])
            self.assertEqual(91, hunt['base'])
            icon = Image.open(out / hunt['icon'])
            self.assertEqual((180, 88), icon.size)
            self.assertEqual(0, icon.getpixel((1, 1))[3], 'the slanted corner is see-through')
            self.assertEqual((255, 255, 255), icon.getpixel((90, 44))[:3], 'the orb in the middle')
            self.assertNotIn('icon', rites.items(str(Path(tmp, 'none')), str(out))[0], 'no export: the cabin icon')


if __name__ == '__main__':
    unittest.main()
