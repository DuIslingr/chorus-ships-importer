"""The chorus_ships mod's sounds: the Forsaken's engine, boost, drift, dodge and travel boost from Chorus's own FMOD Studio
events, for the remake's ships.json "sounds" (ModShipSounds).

The exporter's `fmod` command reads the player's FMOD/Desktop banks: the event paths come from MasterBank.strings.bank, each
event's waves from its timeline (CUE4Parse's EventNodesResolver), decoded by Fmod5Sharp into <work>/fmod/<event>/<wave>.ogg
or .wav, with events.json listing them. Chorus layers and switches waves inside an event by its parameters (rpm, speed,
counters), which aren't read here, so each sound takes the wave(s) of its event that fit the remake's one slot, by name:
the boost's start variations and its loop, the drift's start bursts, its wind loop and the engine re-ignition after it, and
so on (SHIP below).

Volumes: each wave at the remake's own level, measured as the ES2 and GoF3 importers do (a loop's RMS, a one-shot's loudest
60 ms) against the game's engine (0.388 x 0.27), its booster start (0.407 x 0.81) and the boost loop at full strength
(0.343 x 0.6). A wave that would need more than volume 1 is written louder instead (its gain baked in, its peak kept under
0.98). Waves with 4 or 6 channels (Chorus's surround boost layers) are mixed down to stereo. Everything goes into the mod as
Ogg Vorbis through ffmpeg."""
import json, os, re, shutil, subprocess
import numpy as np

ENGINE_LEVEL, SHOT_LEVEL, BOOST_LEVEL, BOOST_LOOP_LEVEL = 0.388 * 0.27, 0.371 * 0.7, 0.407 * 0.81, 0.343 * 0.6

# Per ship: the ships.json sound -> (Chorus event, its waves to take (a pattern), loop?, the level, how the volume and pitch
# run (the slot's from / to: the engine by speed, the boost loop by its strength)).
PHOENIX = 'Sfx/Player/Ships/Phoenix/'
ELDER = 'Sfx/Player/Ships/Elder_Buddy_Engine/'
ARGUS = 'Sfx/Player/Ships/Argus/'
SHIP = {
    'engine':      ('Playership_Phoenix_Engine', r'^Argus3_Engine_Loop_04$', True, ENGINE_LEVEL, (0.55, 1.0), (0.85, 1.15)),
    'boostStart':  ('Playership_Boost', r'^Sfx_Phoenix_Boost_v6_Default_6ch-\d+$', False, BOOST_LEVEL, (1.0, 1.0), (0.95, 1.05)),
    'boostLoop':   ('Playership_Boost', r'^Sfx_Phoenix_Boost_v6_Loop_01$', True, BOOST_LOOP_LEVEL, (0.5, 1.0), (1.0, 1.1)),
    'boostStop':   ('Playership_Boost', r'^SFX_Argus_Boost_Off$', False, BOOST_LEVEL * 0.5, (1.0, 1.0), (0.95, 1.05)),
    'driftStart':  ('Playership_Drift_Start', r'^Amb_LocTrn_15_Energy_Erupt_\d+$', False, BOOST_LEVEL * 0.6, (1.0, 1.0), (0.95, 1.05)),
    'driftLoop':   ('Playership_Drift_Active', r'^Sfx_Flight_Condition_Form_Wind_Cold_05$', True, BOOST_LOOP_LEVEL * 0.6, (0.4, 1.0), (0.9, 1.1)),
    'driftStop':   ('Playership_Drift_Stop_Ignition', r'^Playership_Engine_Ignition_Main_\d+$', False, BOOST_LEVEL * 0.8, (1.0, 1.0), (0.95, 1.05)),
    'dodge':       ('Playership_Dodge_Roll_L', r'^Playership_Engine_Roll_\d+$', False, SHOT_LEVEL * 0.8, (1.0, 1.0), (0.95, 1.05)),
    'travelStart': ('Playership_Travel_Boost', r'^Sfx_Playership_Travelboost_Phoenix_In_C_01$', False, BOOST_LEVEL, (1.0, 1.0), (1.0, 1.0)),
    'travelLoop':  ('Playership_Travel_Boost', r'^Sfx_Phoenix_Travel_Boost_3_Add_Loop$', True, BOOST_LOOP_LEVEL, (0.6, 1.0), (1.0, 1.0)),
    'travelStop':  ('Playership_Travel_Boost', r'^Sfx_Phoenix_Travel_Boost_off_\d+$', False, BOOST_LEVEL * 0.7, (1.0, 1.0), (0.95, 1.05)),
}
# The Elder Buddy (Elder_Buddy_Engine's events; it has no travel boost of its own: the Forsaken's) and the Argus (no drift
# or dash events: its rolls are the dodge).
ELDER_SHIP = {
    'engine':      ('Player_Elder_Engine', r'^Playership_Elder_Buddy_Engine_Loop-001$', True, ENGINE_LEVEL, (0.55, 1.0), (0.85, 1.15)),
    'boostStart':  ('Player_Elder_Boost', r'^Playership_Elder_Buddy_Boost_Ignition$', False, BOOST_LEVEL, (1.0, 1.0), (0.95, 1.05)),
    'boostLoop':   ('Player_Elder_Boost', r'^Playership_Elder_Buddy_Boost_Loop$', True, BOOST_LOOP_LEVEL, (0.5, 1.0), (1.0, 1.1)),
    'boostStop':   ('Player_Elder_Boost', r'^Playership_Elder_Buddy_Boost_Stop$', False, BOOST_LEVEL * 0.5, (1.0, 1.0), (0.95, 1.05)),
    'driftStart':  ('Player_Elder_Drift_Start', r'^Player_elder_Drift_Ignition_\d+$', False, BOOST_LEVEL * 0.6, (1.0, 1.0), (0.95, 1.05)),
    'driftLoop':   ('Player_Elder_Drift_Active', r'^Sfx_Flight_Condition_Form_Wind_Cold_05$', True, BOOST_LOOP_LEVEL * 0.6, (0.4, 1.0), (0.9, 1.1)),
    'driftStop':   ('Player_Elder_Drift_Stop_Ignition', r'^Playership_Engine_Ignition_Main_\d+$', False, BOOST_LEVEL * 0.8, (1.0, 1.0), (0.95, 1.05)),
    'dodge':       ('Player_Elder_Dash', r'^Playership_Elder_Buddy_Dash-\d+$', False, SHOT_LEVEL * 0.8, (1.0, 1.0), (0.95, 1.05)),
}
ARGUS_SHIP = {
    'engine':      ('Argus_Engine', r'^Argus3_Engine_Loop_04$', True, ENGINE_LEVEL, (0.55, 1.0), (0.85, 1.15)),
    'boostStart':  ('Argus_Boost', r'^Sfx_Argus_Boost_v10_Exhaust_Flap_\d+$', False, BOOST_LEVEL, (1.0, 1.0), (0.95, 1.05)),
    'boostLoop':   ('Argus_Boost', r'^Argus_Accelerate_Loop_01$', True, BOOST_LOOP_LEVEL, (0.5, 1.0), (1.0, 1.1)),
    'dodge':       ('Argus_Roll_L', r'^Argus_Reduced_Roll_L-\d+$', False, SHOT_LEVEL * 0.8, (1.0, 1.0), (0.95, 1.05)),
    'travelStart': ('Argus_Travel_Boost', r'^Sfx_Argus_Travelboost_Activate_6ch_01$', False, BOOST_LEVEL, (1.0, 1.0), (1.0, 1.0)),
    'travelLoop':  ('Argus_Travel_Boost', r'^Ship_Argus_TravelBoost_Engine_Loop-001$', True, BOOST_LOOP_LEVEL, (0.6, 1.0), (1.0, 1.0)),
    'travelStop':  ('Argus_Travel_Boost', r'^Ship_Argus_TravelBoost_Stop-\d+$', False, BOOST_LEVEL * 0.7, (1.0, 1.0), (0.95, 1.05)),
}
# ship id -> (its events' folder, its table); a slot it lacks is taken from the Forsaken's.
SHIPS = {'forsaken': (PHOENIX, SHIP), 'elder_buddy': (ELDER, ELDER_SHIP), 'argus': (ARGUS, ARGUS_SHIP), 'forsaken_supercharged': (PHOENIX, {})}   # (the supercharged Forsaken: all the Forsaken's)
# The exporter's event pattern for these.
EVENTS = r'Sfx/Player/Ships/(Phoenix|Elder_Buddy_Engine|Argus)/'


def ffmpeg():
    return shutil.which('ffmpeg')


def read(path):
    """A wave as float32 samples (frames x channels) through ffmpeg."""
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels,sample_rate',
                            '-of', 'csv=p=0', path], capture_output=True, text=True, check=True).stdout.strip().split(',')
    rate, ch = int(probe[0]), int(probe[1])
    raw = subprocess.run([ffmpeg(), '-v', 'error', '-i', path, '-f', 'f32le', '-acodec', 'pcm_f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, ch), rate


def loudness(samples, rate, loop):
    """A loop's RMS, or a one-shot's loudest 60 ms (RMS over the channels' mean)."""
    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
    if loop or len(mono) < rate * 0.06:
        return float(np.sqrt(np.mean(mono ** 2)) + 1e-9)
    win = int(rate * 0.06)
    sq = np.convolve(mono ** 2, np.ones(win) / win, mode='valid')
    return float(np.sqrt(sq.max()) + 1e-9)


def write(src, dst, gain=1.0):
    """src -> dst (Ogg Vorbis): at most two channels, the gain baked in."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    samples, _ = read(src)
    args = [ffmpeg(), '-v', 'error', '-y', '-i', src]
    if samples.shape[1] > 2: args += ['-ac', '2']
    if abs(gain - 1.0) > 1e-3: args += ['-af', f'volume={gain:.4f}']
    subprocess.run(args + ['-c:a', 'libvorbis', '-q:a', '5', dst], check=True)


def build(fmod_dir, mod, ship='forsaken'):
    """ships.json "sounds" for a ship (SHIPS) from <fmod_dir> (the exporter's fmod output); the files go to <mod>/audio/.
    Missing events or waves leave their slot out (the remake keeps the game's sound there); a slot the ship's table lacks
    is the Forsaken's (its files shared). A ship without a table (the player capital ship) keeps the game's sounds."""
    if ship not in SHIPS:
        return {}
    if not ffmpeg():
        print('  no ffmpeg on the PATH: the ships keep the game\'s sounds')
        return {}
    events = json.load(open(os.path.join(fmod_dir, 'events.json'), encoding='utf-8'))
    folder, table = SHIPS[ship]
    out = {}
    for slot, spec in list(table.items()) + [(k, v) for k, v in SHIP.items() if k not in table]:
        event, pattern, loop, level, vol, pitch = spec
        own = slot in table
        waves = events.get('event:/' + (folder if own else PHOENIX) + event, {}).get('waves', [])
        pick = sorted(w for w in waves if re.match(pattern, os.path.splitext(os.path.basename(w))[0]))
        if not pick:
            print(f'  {slot}: no wave in {event}')
            continue
        files, levels = [], []
        for w in pick:
            samples, rate = read(os.path.join(fmod_dir, w))
            levels.append(loudness(samples, rate, loop))
        measured = float(np.median(levels))
        volume = level / measured
        gain = 1.0
        if volume > 1.0:   # louder than an AudioSource plays: bake the rest in, under 0.98 at the peak
            peak = max(float(np.abs(read(os.path.join(fmod_dir, w))[0]).max()) for w in pick) + 1e-9
            gain = min(volume, 0.98 / peak)
            volume = min(1.0, volume / gain)
        for w in pick:
            name = f"audio/{ship if own else 'forsaken'}_" + re.sub(r'[^a-z0-9]+', '_', os.path.splitext(os.path.basename(w))[0].lower()).strip('_') + '.ogg'
            write(os.path.join(fmod_dir, w), os.path.join(mod, name), gain)
            files.append(name)
        entry = {'files' if len(files) > 1 else 'file': files if len(files) > 1 else files[0]}
        v0, v1 = round(volume * vol[0], 3), round(volume * vol[1], 3)
        entry['volume'] = v0 if v0 == v1 else [v0, v1]
        if pitch != (1.0, 1.0): entry['pitch'] = list(pitch)
        out[slot] = entry
    return out
