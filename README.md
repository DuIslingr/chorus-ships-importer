# Chorus ships importer

Builds the **chorus_ships** mod for the Galaxy on Fire 2 Unity Remake from **your own copy of Chorus**. For now that's
the **Forsaken**, Nara's fighter, as a ship sold by visitors in the Space Lounges. It has:
- its own model and Chorus's materials, with the glow lines and engine glow;
- guns on its weapon platforms, a launcher under the nose, and exhausts at its nozzles;
- Chorus's own engine, boost, drift, dodge and travel boost sounds;
- the remake's Chorus flight.

Its three weapons are sold in the shops: the **Forsaken Gatling**, the **Forsaken Laser Rifle** and **Forsaken
Missiles**.

This importer contains **nothing from Chorus**: no models, textures, game data or encryption key, only the code that
reads the files of your own installation. The mod it builds does contain Chorus's models and textures (© Deep Silver
FISHLABS), so it is for your own use: **don't share or upload the built mod**. Share this importer instead.

## What you need

- The **Galaxy on Fire 2 Unity Remake**.
- **Chorus**, installed (Steam, Epic or GOG: the PC game, with its `SpacePrototype/Content/Paks` folder).
- The **.NET 10 SDK** (dotnet.microsoft.com) to build the exporter.
- A checkout of **CUE4Parse** (`git clone https://github.com/FabianFG/CUE4Parse`), the library that reads Unreal
  Engine archives. By default it is expected beside this folder (`../CUE4Parse`); `--cue4parse` points elsewhere.
- **Python 3.9 or newer** with numpy and Pillow (`python3 -m pip install numpy pillow`).
- **ffmpeg** on the PATH, for the sounds. Without it the ship and weapons keep the game's sounds.
- Optional: **Blender** (4.2 or newer) on the PATH or given with `--blender`, for the shop icon and the mod's preview
  image. Without it the ship uses the default icon.

No FModel, no AES key and no mappings file are needed:
- **The key:** Chorus's archive is encrypted. The exporter finds the key in your own copy of the game
  (`Chorus-Win64-Shipping.exe`), the same way key finder tools do.
- **The mappings:** Chorus's packages carry their own property types, so no `.usmap` file is needed.

## Building the mod

```
python3 import.py --game "C:/Program Files (x86)/Steam/steamapps/common/Chorus"
```

The first run builds the exporter (`exporter/`, a small CUE4Parse console program). It then finds the key, exports the
Forsaken's mesh, materials and textures into `chorus_work/`, converts them, and writes `chorus_ships/`. Copy that
folder (or link it) into the remake's **Mods** folder. Later runs reuse the export; `--fresh` exports again.

Settings can also go in `config.json` (copy `config.example.json`); the command line wins.

## What the conversion does

- **Model:** the skeletal mesh becomes a static `.glb` in its rest pose, one primitive per material. It's sized at 3.6×
  Chorus's scale, like the EVERSPACE 2 importer's ships (`modelLength` 749, `modelYaw` 90: Unreal's nose is +X).
- **Materials:** written to `ships.json` "materials" with PNG maps.
  - The colour map is darkened by the baked ambient occlusion.
  - Normal maps are converted from DirectX to Unity (green flipped).
  - The RMO map (roughness, metallic, AO) becomes metallic / smoothness.
  - The emissive masks are baked with each material instance's colours and multipliers.
  - The thrusters' glow follows the engines (`engine`).
- **Mounts:** the guns go on the skeleton's weapon platform bones (`SCK_Weapon_L/R`) and the launcher between the wing
  weapon attach points. The exhausts are found on the mesh, at the thrusters' rear-facing nozzle faces. The cockpit
  view is at the cockpit window bone.
- **Stats:** armour, cargo, handling, slots and price are this importer's choices for an elite fighter. Chorus's own
  numbers don't map onto Galaxy on Fire 2's.
- **Flight:** the Forsaken flies with the remake's **Chorus flight** (`"flightStyle": "chorus"`: forward thrust on Chorus's
  curves, speed-dependent turning, a held boost and a held drift), whatever the player's option. `--flight-style player`
  leaves it to the option; `free` / `original` set another style.

## Sounds

Chorus's sounds are FMOD Studio events in the loose banks of your install (`SpacePrototype/Content/UnleashedPrototype/
FMOD/Desktop`). The exporter reads the event names from `MasterBank.strings.bank`, finds the waves each event plays and
decodes them into `chorus_work/fmod`.

`tools/sounds.py` picks the waves for each of the remake's sound slots from the Forsaken's events:

| Slot | Chorus event |
|---|---|
| engine | Engine |
| boost start / loop / stop | Boost |
| drift start / loop / stop | Drift Start / Active / Stop Ignition |
| dodge | Dodge Roll |
| travel boost start / loop / stop | Travel Boost |

Each sound is set to the game's own level (a loop's loudness, a shot's loudest 60 ms) and written as Ogg Vorbis, with
4- or 6-channel waves mixed down to stereo. Chorus switches waves inside an event by its own parameters (rpm, speed),
which the remake doesn't have, so each slot takes the waves that fit it. `--no-sounds` leaves them out.

## Weapons

`tools/weapons.py` writes `items.json`. The three T1 weapons keep the proportions of Chorus's blueprints, on the scale of
the original items they play like:
- **Gatling:** on the Mass Driver MD 10. The tracers are orange and it uses Chorus's gatling loop.
- **Laser rifle:** on the Berger Converge IV. It fires Chorus's 25-damage shots every 0.9 s, 0.62 of the gatling per
  second, as in Chorus.
- **Missiles:** a secondary on the Intelli Jet, fired in pairs, faster, red.

In Chorus all three are primaries. Galaxy on Fire 2 has no missile primaries, so the launcher fires secondary missiles.
The weapon models aren't on the mounts: that needs the ship as a ship kit.

## Tests

```
python3 -m unittest discover -s tests
```

They check the conversions on synthetic data and need no game files.
