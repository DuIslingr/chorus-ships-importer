#!/usr/bin/env python3
"""Builds the chorus_ships mod for the Galaxy on Fire 2 Unity Remake from your own copy of Chorus.

    python3 import.py --game "<Chorus install folder>" [--out chorus_ships] [--cue4parse <CUE4Parse checkout>] [--mobile] [--zip]

Steps: build the exporter (.NET, CUE4Parse) -> find the pak's AES key in your game's exe -> export the ships' meshes,
materials and textures -> convert them -> write the mod (mod.json, ships.json, models/, maps/, icons/, preview.png).
Settings may also come from config.json (see config.example.json); the command line wins. --mobile: also a lighter
version for phones in <out>_phone and <out>_phone.zip (Blender decimates the models to --ratio of their triangles, the
textures are halved: tools/mobile.py). --zip: also zip the desktop mod.
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tools import ships, sounds, weapons, kit, npcs, mi, rig, turrets, world, mobile  # noqa: E402

MASTER_DATA = 'SpacePrototype/Content/UnleashedPrototype/Core/PlayerEquipment/BP_PlayerEquipmentMasterData.uasset'
EXPORTS = [ships.PHOENIX + '/skelmesh/SK_Phoenix',      # what the mod needs from the pak (materials and textures come along)
           ships.PHOENIX + '/T_Phoenix_center_moveable_D',  # (MI_Phoenix_center_Moveable takes these from its parent)
           ships.PHOENIX + '/T_Phoenix_center_moveable_N'] + kit.EXPORTS + ships.ARGUS_EXPORTS + npcs.EXPORTS + turrets.EXPORTS
# (the weapon models, tools/kit.py; the Argus) and the Elder Buddy's material instances, which bring their textures:
MATERIAL_EXPORTS = ships.ELDER_EXPORTS


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
    ap.add_argument('--no-kit', action='store_true', default=cfg.get('no_kit', False),
                    help="a plain ship, without the ship kit that shows Chorus's weapon models on it")
    ap.add_argument('--mobile', action='store_true', default=cfg.get('mobile', False),
                    help='also make a lighter version for phones (needs Blender): <out>_phone and its zip')
    ap.add_argument('--ratio', type=float, default=cfg.get('ratio', 0.25),
                    help='the phone version keeps this share of the triangles (default 0.25)')
    ap.add_argument('--zip', action='store_true', default=cfg.get('zip', False), help='also zip the desktop mod')
    ap.add_argument('--no-world', action='store_true', default=cfg.get('no_world', False),
                    help="leave out the Chorus systems (skies, planets: tools/world.py)")
    ap.add_argument('--bake-hulls', action='store_true', default=cfg.get('bake_hulls', False),
                    help="bake the NPC hulls' trim sheets into one texture set each (for a remake without Chorus's layers)")
    ap.add_argument('--no-sounds', action='store_true', default=cfg.get('no_sounds', False),
                    help="leave Chorus's sounds out (the ship plays the game's)")
    ap.add_argument('--fresh', action='store_true', default=cfg.get('fresh', False), help='export again even if the work folder has it')
    a = ap.parse_args()
    if not a.game: ap.error('--game: the Chorus install folder')
    return a


def exporter(a):
    dll = os.path.join(HERE, 'exporter', 'bin', 'Release', 'net10.0', 'ChorusExport.dll')
    src = os.path.join(HERE, 'exporter', 'Program.cs')
    if not os.path.exists(dll) or os.path.getmtime(src) > os.path.getmtime(dll):   # (first run, or its source changed)
        print('Building the exporter...')
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
    if a.fresh or not all(os.path.exists(os.path.join(export, p + ('.png' if '/T_' in p else '.glb'))) for p in EXPORTS) \
            or not all(os.path.exists(os.path.join(export, p + '.json')) for p in MATERIAL_EXPORTS):
        os.makedirs(a.work, exist_ok=True)
        lst = os.path.join(a.work, 'export_list.txt')
        open(lst, 'w').write('\n'.join(EXPORTS + MATERIAL_EXPORTS) + '\n')
        print('Exporting from the pak...')
        run('export', lst, export)
    master = os.path.join(a.work, 'PlayerEquipmentMasterData.json')   # the weapons' names and descriptions
    if a.fresh or not os.path.exists(master):
        run('json', MASTER_DATA, master)
    fmod = os.path.join(a.work, 'fmod')
    if not a.no_sounds and (a.fresh or not os.path.exists(os.path.join(fmod, 'events.json'))):
        print("Exporting the ship's sounds from the FMOD banks...")
        run('fmod', sounds.EVENTS + '|' + weapons.EVENTS, fmod)

    if os.path.exists(a.out): shutil.rmtree(a.out)
    os.makedirs(a.out)
    # the material instances' parameters through their parents (tools/mi.py: one exporter run per generation)
    resolver = mi.Resolver(run, os.path.join(a.work, 'mi'))
    resolver.prefetch([p for _, p, _ in ships.FORSAKEN_MATERIALS + ships.ELDER_MATERIALS] +
                      [ships.ARGUS + '/' + m for m in ships.ARGUS_MATERIALS] + npcs.material_paths(export))
    resolver.fetch_textures(npcs.texture_paths(resolver, export), export)   # (maps an instance inherits from its parents)
    anim_dir = os.path.join(a.work, 'anims')   # Chorus's drift clips for the Forsaken (tools/rig.py)
    if a.fresh or rig.load(anim_dir) is None:
        lst = os.path.join(a.work, 'anim_list.txt')
        open(lst, 'w').write('\n'.join(rig.EXPORTS) + '\n')
        run('anim', lst, anim_dir, capture=True)
    anims = rig.load(anim_dir)
    print('Converting the Forsaken...')
    forsaken = ships.forsaken(export, a.out, resolver, anims)
    print('Converting the Elder Buddy and the Argus...')
    elder = ships.elder_buddy(export, a.out, forsaken, resolver)
    argus = ships.argus(export, a.out, resolver)
    entries = [forsaken, elder] + ([argus] if argus else [])
    print("Converting Chorus's enemy ships for the traffic...")
    npcs.CHORUS_LAYERS = not a.bake_hulls
    enemies = npcs.build(export, a.out, resolver, work=a.work, anims=anims)
    players = [e for e in enemies if 'lounge' in e]   # (the supercharged Forsaken: sold, with sounds and an icon)
    enemies = [e for e in enemies if 'lounge' not in e]
    entries += players
    for e in entries:
        if a.flight_style == 'player': e.pop('flightStyle', None)
        else: e['flightStyle'] = a.flight_style
    if not a.no_sounds:
        print('Converting the sounds...')
        for e in entries:
            snd = sounds.build(fmod, a.out, e['id'])
            if snd: e['sounds'] = snd
    print("Writing the Forsaken's weapons...")
    items = weapons.build(fmod if not a.no_sounds else '', a.out, master)
    print("Converting Chorus's turrets...")
    items += turrets.build(export, a.out, resolver)   # (the capital ships' npcTurrets: npcs.CHORUS_TURRETS)
    if not a.no_world:
        print("Converting Chorus's regions (skies, planets) into the Chorus systems...")
        world.build(export, a.out, resolver, run, ships=enemies)   # (its wreck fields' hulks: the NPC ships)
    json.dump(items, open(os.path.join(a.out, 'items.json'), 'w', encoding='utf-8'), indent=1)
    json.dump(entries, open(os.path.join(a.out, 'ships.json'), 'w', encoding='utf-8'), indent=1)
    json.dump({'id': 'chorus_ships', 'name': 'Chorus Ships', 'version': '0.1', 'author': 'DuIslingr',
               'description': "Ships from Chorus: the Forsaken, sold by visitors in the Space Lounges, with its gatling, laser "
                              "rifle and missiles in the shops, and Chorus's own sounds.",
               'credits': 'Models and textures: Chorus (c) Deep Silver FISHLABS. Built from your own copy; for personal use.',
               'preview': 'preview.png',
               # generated images and Ogg encoding differ between computers: two players' builds still count as the same mod
               'multiplayerIgnore': ['maps/', 'icons/', 'preview.png', 'audio/', 'skies/', 'planets/']}, open(os.path.join(a.out, 'mod.json'), 'w', encoding='utf-8'), indent=1)
    open(os.path.join(a.out, 'README.txt'), 'w').write(
        'Chorus Ships, built by chorus_ships_importer from your own copy of Chorus.\n'
        "It contains Chorus's models and textures (c) Deep Silver FISHLABS: for your own use, don't share or upload it.\n")

    if a.blender:
        print('Rendering the icon and preview...')
        os.makedirs(os.path.join(a.out, 'icons'), exist_ok=True)
        for e in entries:
            subprocess.run([a.blender, '-b', '--factory-startup', '-P', os.path.join(HERE, 'tools', 'render_blender.py'), '--',
                            a.out, e['id'], 'preview.png' if e['id'] == 'forsaken' else ''],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from PIL import Image
        for e in entries:   # rendered at twice the size, then scaled to the shop's 180 x 88
            p = os.path.join(a.out, e['icon']); Image.open(p).resize((180, 88), Image.LANCZOS).save(p, optimize=True)
    else:
        print('No Blender: the ship uses the default shop icon and the mod has no preview image.')
        for e in entries: e.pop('icon', None)
        json.dump(entries, open(os.path.join(a.out, 'ships.json'), 'w', encoding='utf-8'), indent=1)
    if not a.no_kit:
        # After the render (it draws the plain ship): the Forsaken as a ship kit with its weapon models (tools/kit.py).
        print('Writing the ship kit and its weapon models...')
        kits, kit_ships = kit.build(export, a.out, forsaken, skinned=[elder])
        entries = kit_ships + ([argus] if argus else []) + players
        json.dump(kits, open(os.path.join(a.out, 'shipkits.json'), 'w', encoding='utf-8'), indent=1)
    capitals = npcs.npc_ships(enemies)   # (their ships.json traffic set to 0: npcships.json spawns them, with escorts)
    json.dump(capitals, open(os.path.join(a.out, 'npcships.json'), 'w', encoding='utf-8'), indent=1)
    entries += enemies   # (no icons or sounds: only the traffic flies them)
    json.dump(entries, open(os.path.join(a.out, 'ships.json'), 'w', encoding='utf-8'), indent=1)
    print(f'Done: {a.out}. Copy (or link) it into the remake\'s Mods folder.')
    if a.zip:
        print(f'  zipped: {mobile.zip_folder(a.out, a.out.rstrip(os.sep) + ".zip")}')
    if a.mobile:
        print('Making the phone version...')
        phone = mobile.make_mobile(a.out, a.out.rstrip(os.sep) + '_phone', a.ratio, a.blender)
        print(f'  the phone version: {mobile.zip_folder(phone, phone + ".zip")} (on a phone: Mods > Import mod, and pick it)')


if __name__ == '__main__':
    main()
