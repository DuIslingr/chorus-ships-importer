# Roadmap

Done:
- The Forsaken: model, materials with glow lines and engine glow, guns / launcher / exhaust mounts, cockpit, icon,
  preview.
- The exporter finds the pak key itself.
- 2026-11-11:
  - the remake's Chorus flight (`flightStyle`);
  - Chorus's engine, boost, drift, dodge and travel boost sounds (FMOD events, `fmod`);
  - the three T1 weapons as items, with Chorus's shot sounds and colours;
  - all fifteen weapons (T2 / T3, Chorus's names), the Forsaken as a ship kit with its gun models, the Elder Buddy (a kit
    skin) and the Argus with their own sounds, eight enemy ships in the traffic, `tools/sheet.py`;
  - the materials read through their parents (`tools/mi.py`), the tangents' handedness fixed, the Elder's and the Argus's
    glow as Chorus sets it;
  - every other ship: about seventy NPC hulls as traffic fighters, pirate bosses, freighters and capital ships, their
    trim-sheet materials baked.

Next, roughly in order:
1. **Check in the remake.** Load the mod and look at the ship: orientation, size, mounts, materials. Then tune
   `glowSize`, the hangar height and the camera.
2. **Listen in the game** and tune the sound volumes and pitch ranges, and the weapons' balance.
3. **The NPC ships in the game:** their turrets (`npcTurrets` and turret mounts for the capital ships), exhaust mounts at
   their real nozzles, escorts and spawns (`npcships.json`), their weapons and NPC flight from Chorus's NPC steering.
4. **Check the guesses** against Chorus in motion: the trim emissive's UV-shift mask, the LayerData channels (metalness
   from red), the Argus's vertex colours, the Elder's edge kicker (a red rim far away, left out).
