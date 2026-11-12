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
    trim-sheet materials baked; names from their NPC blueprints; Sav's and Ree's layered coats, the Disruptor nose first;
  - the Forsaken's drift animation (its rigid skin as parts on the skeleton, Chorus's clips; the remake's ships.json
    `animations`), on the Elder Buddy and the supercharged Forsaken too; the supercharged Forsaken's energy wings;
  - its travel boost clips and its steering / thrust / brake flaps as poses by the input; the energy wings shimmer
    (the remake's shimmer layer with Chorus's soft noise);
  - the NPC hulls' exhausts at their Thruster sockets or their thruster glow's nozzles, the capital ships' turrets
    (Artillery / NPCAttack sockets, else spots along the back; npcTurrets 48, the Vossk 49), damage smoke at the
    warships' VFX_DT sockets; npcships.json: the capital ships with escorts of their side's fighters, spawn chances,
    the dropship launching Circle fighters;
  - checked against gameplay footage: the Forsaken's cyan glow lines (match); the Trom Shipyard frigates' light-grey
    plating against our muddy, half-metal frigate: metalness now from LayerData's blue (a near-binary flag);
  - the Forsaken's other animations: the weapons deploying (layer 1, while firing and 3 s after; the kit's primary
    guns ride the wpnPlatform bones, ships.json mount `follow`), banking with the steering (poses, root left out), the
    dash's dodge roll and its own dodge out of a drift (layer 3); every layered clip keys only the bones that differ
    from Chorus's idle;
  - the Prophet checked against a screenshot (upright, its blade below, as built): its crystal crown glows red (M_JTU_Blend's
    inner glow), its lights take its blueprint's override (blue); windows drawn as their panes (the pane atlas, the
    window master's glass mask) instead of solid glowing slabs; the shuttle's plating found (a case mismatch in its name);
  - decals cut out of their sheets (hull numbers, emblems); Guilt's shell masked to its shape; the bat swarm's bone from
    its own maps; the Prophet's four weapon pods on its sockets and its thrusters (blueprint parts: S(..., attach=));
    the palette's LayerData blue stays metal (footage of the Prophet in its arena: its white swatches black).
  - the trim and plating masters decompiled (their base-pass pixel and vertex shaders, npcs.py TRIM_SHADER /
    PLATING_SHADER): the palette by UV set 3 as read, metal = saturate((LayerData.b - 0.5) x 2 + the RMO's metal),
    roughness lerp(LayerData.r, .g) by the RMO, the trim's tiling diffuse / RMO over UV set 1 x Base UV Tile Amount
    (left out before). The Prophet's red head and black V are its arena in its mirror plates: the head (palette cell
    4) and the V (cell 0) are glossy off-white metal, the head's plates facing up into the arena's red glow, the V
    facing the dark fog; rendered under a red-overhead sky, the importer's maps give the footage's look. In a remake
    system the head reflects that system's sky instead (dark in most).
  - the remake's **Chorus layers** (GoF2/Hull ChorusLayers, a material's `chorus` block; remake ChorusLayersTests): the
    trim and plating hulls drawn from Chorus's maps over their own UV sets instead of a bake (the warships' trim detail
    was lost at metres a texel): M_NPCShipTrimMaster's accent strips, UV-shift emissive (UV3.v < 0, compiled; the bake
    read UV0), 2x near emission, far kicker rim and distance boost; the Cult / TER trim's dirt; the plating. Shared maps
    in maps/chorus/. Tech panels from their own maps. The Omen's faceless tissue as its shader draws it: all glow on a
    black base (its compiled base pass), not a lit dark red. The SM_TU_Ufo placeholder dropped (no material in the pak).
  - Guilt re-examined (BP_NPC_Guilt, M_Guilt_Shell's compiled base, depth and vertex passes): drawn at its blueprint's
    0.17 (a 170 m boss, not a 987 m capital ship), its inner and outer shells apart (black, half metal; each shell's
    dissolve mask; the outer pushed out; the inner's red specks), its core (M_Warpin_Omen_Portal) an additive glow;
    the blueprints' mesh scales applied (the Support Ship's 0.9).
  - Guilt animated: kept skinned (the remake's ships.json "skinned") with A_Guilt_Idle03, its shells by the remake's
    Chorus shell (flowing dissolve, the push in the vertex shader, the inner glow), its core through C_Omen_Warp; the Omen
    Support's idle (rigid parts); the blueprints' thrusters and the gunships' gun pod / mine thrower; the material
    resolver's parent chains guarded against cycles (M_DecalMaster_Emissive names its own instance: a build hung).

Next, roughly in order:
1. **Check in the remake.** Load the mod and look at the ship: orientation, size, mounts, materials. Then tune
   `glowSize`, the hangar height and the camera.
2. **Listen in the game** and tune the sound volumes and pitch ranges, and the weapons' balance.
3. **NPC flight from Chorus's NPC steering** and their own weapons (they fly with the remake's NPC hulls and guns).
4. **Still unchecked against Chorus** (no footage shows them clearly; they rest on reading the materials): the trim
   emissive's UV-shift mask; which colour of Sav's and Ree's layer mask picks which coat (they are allies' large ships
   in "Defend the Naiara Citadel", BP_NPC_Ship_Sav / _Ree confirm SM_Sav / SM_Ree, but neither hull is in frame long
   enough); the Elder ship's / Elder Buddy's glow and edge kicker (Rasar's ship stays far off); the TER military
   palette once rebuilt with the blue-channel metalness; the Argus never appears (a player ship the game doesn't let
   you fly). Next way in: the shaders' compiled HLSL in the pak's shader library, or someone's own captures.
5. **Look at the Forsaken's animations in the remake:** the weapon doors and guns while firing, the bank, the dodge;
   tune the pose rate and the 3 s weapons hold.
6. **Station lights' channels:** their vertex colours' red steps (0.21, 0.5, 0.58, 0.74, 1) pick among four colours;
   which step is which isn't in the cooked files (they stay the first channel). Footage of lit freighters would tell.
7. **Still read by parameter names, to decompile the same way** (the exporter's `shaders`, then d3dcompiler): the faceless cores (Enable Core) and the
   breath curve (CA_BaseVFX, a curve atlas the exporter doesn't write: the bake takes it at rest). (M_JTU_Blend, the
   Prophet's crown, and the Omen tissue's pulse, parallax and scroll are done: the remake's Chorus layer kinds "crystal"
   and "tissue", tools/npcs.py _jtu_crystal / _faceless_tissue; the crystal's turbulence is a value noise standing in for
   Unreal's noise texture; the tissue's warp-in dissolve edge is left out. M_Phoenix's glow lines are done too: decompiled, the Emissive02 Min / Max wave along the hex pattern,
   the remake's "wave" block, tools/ships.py _wave; its hit flash and AFX pattern left out.) The Omen tissue's pulse, parallax and scroll and the faceless dissolve edge
   would want a remake shader like the Chorus layers. Guilt's shell normal (the base pass's, from the flowing noise) is
   left flat, and its shadow is the whole, unpushed shell; the core's portal threads are a scrolling glow, not the
   portal's own formula (M_Warpin_Omen_Portal not decompiled).
8. **The other trim permutations:** decompiled so far: the Cult's trim (no emissive, no kicker), the Cult's emissive
   trim (MI_TER_TechTrim03_Cult_Emissive: UV-shift emissive, dirt, no kicker), the fighters' M_NPCShipTrimMaster
   (MI_TER_NPC_Ship02: accent, emissive, kicker). A TrimLayers instance with "Enable Accent 1 (Wear)" on is drawn with
   the fighters' accent formula, unchecked; the Disruptor's emissive trim not dumped. Guilt's radial portal core is
   still left out.
9. **Smaller things:** rename the "Terran Gunship" ("Terran" is only Chorus's internal file tag); decide whether Chorus
   freighters stay out of the Vossk / Nivelian / Midorian systems; the Sentinels' near-black bones; smaller bakes for the
   freighters (the mod is about 500 MB).
11. **Guilt as Chorus plays it** (left out of the mod: not a ship): an invincible pursuer for the remake's event graphs
   or a special encounter: it picks the player and chases at stepped speeds (BT_Guilt: x0.5 up to x3 / x5 / x7, inside
   its area), its proximity screen effect (PP_Guilt) within 1.5 km, its wither (BP_Guilt_Debuff, MaxWither 5) within
   160 m, stopped or parked by the mission (MTAction_ManageGuiltNPC). Needs a new NPC behaviour in the remake.
10. **Level-placed parts and wrecks:** the capital ships' thrusters are placed by Chorus's levels (read the .umap actors
   that place them); the wreck skeletal meshes and their explosion anim blueprints (ships breaking apart) would need the
   remake to swap a destroyed mod ship for its wreck.
13. **Warships, done further** (`tools/warships.py`): the death throes (BP_<Size>Warship_Base's PhaseDuration and
    ExplosionDamageRadius, "deathThroes"), the barriers blocking the way in ("shieldBlocks"), the shielded turret mounts'
    own shields ("shield" 0.75), the other configurations as ships of their own (Small C, Medium B with an Omen hangar,
    Medium C). Still the remake's: the parts' share of the hull, to tune in play.
16. **Death explosions, still open** (`tools/explosions.py`): the lights-only emitters (Chorus's flash lights), the
    impostor debris (MI_ImposterDebris's sheet isn't in its instance), trails spawned along a path and vector fields are
    left out; the fireball's smoke is added (its dark coverage isn't drawn); the death effect configs' timing (a 5 s
    tumble before the main blast) is the remake's own dying time; the brightness squeeze (8 / (8 + x)) wants checking.
15. **Wrecks, still open** (`tools/wrecks.py`; the player's own, SK_PhoenixWreck / _Buddy / SK_TF_Argus_Wreck, are
    given now, `apply_players`): the wrecks' burning and dissolving materials (MF_WreckBurn / MF_WreckDisintegrate) are drawn as the converter makes them,
    not animated; the gunship's gun pod and mine wrecks (ABP_Explosion_TG_Gunship_Wreck_GunPod / _Mine) left out.
14. **The player capital ship, done** (`tools/capital.py`): the Shield Overcharge (device 22), the hull regeneration
    ("hullRegen"), the Death Ray as a wide beam held on (beamRadius / beamReach, its heat), all 14 artillery barrels as
    turret slots, the braking flaps (its own model from SK_PlayerControlledLargeShip01, the LoopBraking pose) and its shop
    icon (render_blender.py "fit"). Left: Chorus's Braking / StopBraking clips as the flaps' opening and closing (the pose
    follows the brake input instead), the Death Ray's 1 s charge-up and the shield overcharge's own effect
    (BP_Effect_Auxiliary_Shield_PlayerCapitalShip); its stats are this importer's balance, to tune in play.
12. **The Chorus systems, next areas:** Nimika Prime's broken planet (SM_Planet_Destroyed_LocAST parts, M_Planet_Broken),
    Stega Belt's and the Tarris Wormhole's own stations (or other levels' structures: LocASP03's military platform,
    LocRSB14's antenna array), then the bosses, wrecks and effects that need the remake (the rift look and Nimika's dormant
    Rift are done: tools/rift.py; the vortex's world position offset and the rift's own bottom material,
    M_PortalRift_BOTTOM, are left out; its exposure 0.4 wants checking in the remake). Check
    the skies', planets', stations' and rocks' brightness and size against Chorus in the remake (Chorus's auto exposure
    isn't there; the magma rocks' Master Brightness makes them very dark). The stations are 80-120 MB each: a lower
    triangle budget or quantised positions if the mod's size matters.
