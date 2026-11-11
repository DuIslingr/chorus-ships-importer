"""The conversions the importer relies on, on synthetic data (no game files): Unreal's export frame -> the remake's
mounts, Chorus's RMO / normal / emissive maps -> URP's, the nozzle finder, and the glb round trip."""
from pathlib import Path
import sys, tempfile, os, unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import ships, textures, glb, sounds, weapons


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


class WeaponTests(unittest.TestCase):
    def test_items_without_an_export_keep_their_base_sounds(self):
        with tempfile.TemporaryDirectory() as d:
            items = weapons.build('', d)
        self.assertEqual(['chorus_gatling', 'chorus_laser_rifle', 'chorus_missiles'], [i['id'] for i in items])
        self.assertEqual([27, 8, 37], [i['base'] for i in items])   # Mass Driver MD 10, Berger Converge IV, Intelli Jet
        for i in items:
            self.assertNotIn('shot', i.get('fx', {}))
        gat, laser = items[0]['stats'], items[1]['stats']
        ratio = (laser['damage'] / laser['loadingTimeMs']) / (gat['damage'] / gat['loadingTimeMs'])
        self.assertAlmostEqual(83 / 133, ratio, delta=0.02)   # Chorus's laser rifle / gatling per second


if __name__ == '__main__':
    unittest.main()
