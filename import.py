#!/usr/bin/env python3
"""Builds the chorus_ships mod for the Galaxy on Fire 2 Unity Remake from your own copy of Chorus.

    python3 import.py --game "<Chorus install folder>" [--out chorus_ships] [--cue4parse <CUE4Parse checkout>]

Steps: build the exporter (.NET, CUE4Parse) -> find the pak's AES key in your game's exe -> export the ships' meshes,
materials and textures -> convert them -> write the mod (mod.json, ships.json, models/, maps/, icons/, preview.png).
Settings may also come from config.json (see config.example.json); the command line wins.
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tools import ships, sounds, weapons  # noqa: E402

EXPORTS = [ships.PHOENIX + '/skelmesh/SK_Phoenix',      # what the mod needs from the pak (materials and textures come along)
           ships.PHOENIX + '/T_Phoenix_center_moveable_D',  # (MI_Phoenix_center_Moveable takes these from its parent)
           ships.PHOENIX + '/T_Phoenix_center_moveable_N']


def options():
    cfg = {}
    if os.path.exists(os.path.join(HERE, 'config.json')):
        cfg = {k: v for k, v in json.load(open(os.path.join(HERE, 'config.json'))).items() if not k.startswith('_')}
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--game', default=cfg.get('game'), help='the Chorus install folder (the one with Chorus.exe / SpacePrototype)')
    ap.add_argument('--out', default=cfg.get('out', os.path.join(HERE, 'chorus_ships')), help='the mod folder to write')
    ap.add_argument('--work', default=cfg.get('work', os.path.join(HERE, 'chorus_work')), help='where the export goes')
    ap.add_argument('--cue4parse', default=cfg.get('cue4parse', os.path.join(HERE, '..', 'CUE4Parse')), help='a CUE4Parse checkout')
    ap.add_argument('--dotnet', default=cfg.get('dotnet') or shutil.which('dotnet') or os.path.expanduser('~/.dotnet/dotnet'))
    ap.add_argument('--blender', default=cfg.get('blender') or shutil.which('blender'), help='Blender, for the icon and preview (optional)')
    ap.add_argument('--key', default=cfg.get('key'), help='the pak key (0x...), if the scan of the exe should be skipped')
    ap.add_argument('--flight-style', default=cfg.get('flight_style', 'chorus'), choices=['chorus', 'free', 'original', 'player'],
                    help="how the ships fly in the remake: Chorus's flight (default), free flight, the original, or the player's option")
    ap.add_argument('--no-sounds', action='store_true', default=cfg.get('no_sounds', False),
                    help="leave Chorus's sounds out (the ship plays the game's)")
    ap.add_argument('--fresh', action='store_true', default=cfg.get('fresh', False), help='export again even if the work folder has it')
    a = ap.parse_args()
    if not a.game: ap.error('--game: the Chorus install folder')
    return a


def exporter(a):
    dll = os.path.join(HERE, 'exporter', 'bin', 'Release', 'net10.0', 'ChorusExport.dll')
    if not os.path.exists(dll):
        print('Building the exporter (first run)...')
        subprocess.run([a.dotnet, 'build', '-c', 'Release', '-nologo', '-v', 'q', f'-p:CUE4ParseDir={os.path.abspath(a.cue4parse)}'],
                       cwd=os.path.join(HERE, 'exporter'), check=True)
    def run(*args, capture=False):
        env = dict(os.environ, CHORUS_GAME=a.game, CHORUS_AES_KEY=a.key or '')
        r = subprocess.run([a.dotnet, dll, *args], env=env, check=True, text=True,
                           stdout=subprocess.PIPE if capture else None, stderr=subprocess.DEVNULL if capture else None)
        return r.stdout.strip() if capture else None
    return run


def main():
    a = options()
    run = exporter(a)
    if not a.key:
        print('Finding the pak key in the game exe...')
        a.key = run('keyscan', capture=True)
    export = os.path.join(a.work, 'export')
    if a.fresh or not os.path.exists(os.path.join(export, ships.PHOENIX, 'T_Phoenix_center_moveable_N.png')):
        os.makedirs(a.work, exist_ok=True)
        lst = os.path.join(a.work, 'export_list.txt')
        open(lst, 'w').write('\n'.join(EXPORTS) + '\n')
        print('Exporting from the pak...')
        run('export', lst, export)
    fmod = os.path.join(a.work, 'fmod')
    if not a.no_sounds and (a.fresh or not os.path.exists(os.path.join(fmod, 'events.json'))):
        print("Exporting the ship's sounds from the FMOD banks...")
        run('fmod', sounds.EVENTS + '|' + weapons.EVENTS, fmod)

    if os.path.exists(a.out): shutil.rmtree(a.out)
    os.makedirs(a.out)
    print('Converting the Forsaken...')
    entries = [ships.forsaken(export, a.out)]
    for e in entries:
        if a.flight_style == 'player': e.pop('flightStyle', None)
        else: e['flightStyle'] = a.flight_style
    if not a.no_sounds:
        print('Converting the sounds...')
        snd = sounds.build(fmod, a.out)
        if snd: entries[0]['sounds'] = snd
    print("Writing the Forsaken's weapons...")
    items = weapons.build(fmod if not a.no_sounds else '', a.out)
    json.dump(items, open(os.path.join(a.out, 'items.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(entries, open(os.path.join(a.out, 'ships.json'), 'w', encoding='utf-8'), indent=1)
    json.dump({'id': 'chorus_ships', 'name': 'Chorus Ships', 'version': '0.1', 'author': 'DuIslingr',
               'description': "Ships from Chorus: the Forsaken, sold by visitors in the Space Lounges, with its gatling, laser "
                              "rifle and missiles in the shops, and Chorus's own sounds.",
               'credits': 'Models and textures: Chorus (c) Deep Silver FISHLABS. Built from your own copy; for personal use.',
               'preview': 'preview.png',
               # generated images and Ogg encoding differ between computers: two players' builds still count as the same mod
               'multiplayerIgnore': ['maps/', 'icons/', 'preview.png', 'audio/']}, open(os.path.join(a.out, 'mod.json'), 'w', encoding='utf-8'), indent=1)
    open(os.path.join(a.out, 'README.txt'), 'w').write(
        'Chorus Ships, built by chorus_ships_importer from your own copy of Chorus.\n'
        "It contains Chorus's models and textures (c) Deep Silver FISHLABS: for your own use, don't share or upload it.\n")

    if a.blender:
        print('Rendering the icon and preview...')
        os.makedirs(os.path.join(a.out, 'icons'), exist_ok=True)
        subprocess.run([a.blender, '-b', '--factory-startup', '-P', os.path.join(HERE, 'tools', 'render_blender.py'), '--',
                        a.out, 'forsaken'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from PIL import Image
        for e in entries:   # rendered at twice the size, then scaled to the shop's 180 x 88
            p = os.path.join(a.out, e['icon']); Image.open(p).resize((180, 88), Image.LANCZOS).save(p, optimize=True)
    else:
        print('No Blender: the ship uses the default shop icon and the mod has no preview image.')
        for e in entries: e.pop('icon', None)
        json.dump(entries, open(os.path.join(a.out, 'ships.json'), 'w', encoding='utf-8'), indent=1)
    print(f'Done: {a.out}. Copy (or link) it into the remake\'s Mods folder.')


if __name__ == '__main__':
    main()
