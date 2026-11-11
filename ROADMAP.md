# Roadmap

Done:
- The Forsaken: model, materials with glow lines and engine glow, guns / launcher / exhaust mounts, cockpit, icon,
  preview.
- The exporter finds the pak key itself.
- 2026-11-11:
  - the remake's Chorus flight (`flightStyle`);
  - Chorus's engine, boost, drift, dodge and travel boost sounds (FMOD events, `fmod`);
  - the three T1 weapons as items, with Chorus's shot sounds and colours.

Next, roughly in order:
1. **Check in the remake.** Load the mod and look at the ship: orientation, size, mounts, materials. Then tune
   `glowSize`, the hangar height and the camera.
2. **Listen in the game** and tune the sound volumes and pitch ranges, and the weapons' balance.
3. **Weapon models on the mounts:** the Forsaken as a ship kit with hardpoint models (`SK_Gatling_01`, `SK_laser_01`,
   `SK_missile_launcher_01`).
4. **The T2 / T3 weapons** (A and B variants) as more items.
5. **Enemy ships in the traffic:** the Circle's fighters and the Rift ships, `traffic` races.
6. **Other player ships:** Argus (`BP_Player_Ship_Argus`, `TF_Argus`) and the Elder Buddy.
