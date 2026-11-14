"""Chorus's world encounters GoF2, GoF3 and EVERSPACE 2 have no counterpart for, as the mod's bar missions
(events/chorus_*.gof2mission, the remake's text missions: Modding/README.md "Story missions and bar missions"), offered in
the Chorus systems' Space Lounges and taken again and again (Chorus places each encounter once; its templates are generic).

Chorus's encounter templates (Mission/Encounters/BaseTemplates: MT_E*_Base) against the remake's missions (the user,
2026-11-14: "compare to existing missions pulled from es2 gof3 and gof2 before taking any"):
  Escort (MT_EEscort_Base)            GoF2's Escort, left out
  Salvage (MT_ESalvage_Base)          GoF2's Recovery / Salvage, ES2's Hidden Stash / Resource Depot / Cargo Drone, left out
  Skirmish (Pirates / Cult / Faceless) GoF2's Pirate hunting / Defense, ES2's Battle Support, left out
  NPC vs NPC                          ES2's Battle Support, left out
  Omen Tear (MT_EOmenTear_Base)       new: Faceless Manifestation
  Civilian (MT_ECivilian_Base)        its stay-near task is GoF3's (Errand Boy, Weapon Control) and its help ES2's Ship In
                                      Need, but neither is offered in the bars: Civilian Assistance (the user: "do both")
Text only (the user: "we dont need voiced lines"): Chorus's objective lines (the trees' SourceStrings), the offers in the
mod's own words. Times and pay are GoF2's measure (a ship's ~2.5 units/ms, GoF2's freelance pay).

Faceless Manifestation (MT_EOmenTear_Base with BP_OmenManifestation, BP_OmenTear): "Stop the manifestation": the fractures
(the tears, BP_OmenTear: short-range scannable; the tree counts "Closed fractures" to 5) closed by flying into each one
before the "Manifestation in" countdown (its whiteboard's 60 s) runs out; the Faceless that come through destroyed ("Destroy
Facless entities": ActorAmount 4); its reward a Rite Energy Fragment, here Void Crystals (the remake's Void energy fuel).
Two Omen drones meet the player at the start (the tree's 20 s timer brings its first).
Civilian Assistance (MT_ECivilian_Base): "Distress Signal", "Contact civilian ship", then one of three tasks at random (its
RandomMission switch): "Transfer fuel to civilian ship", "Counter hack the civilian ship's system", "Calibrate the civilian
ship's systems", each a 10 s stay in the ProgressZone beside the ship (MTAction_ProgressSubObjective ProgressTime 10); the
ship warps out after (MTAction_WarpOutNPC). The remake: the mod's Chorus civilian hull, holding still; destroyed, failed.
"""
import json, math, os, random

MOD = 'chorus_ships'
STATIONS = ['the_enclave', 'stega_belt', 'helios', 'eos', 'nimika_prime', 'achunal_labs', 'tarris_wormhole']   # (tools/world.py)
OMEN = f'{MOD}:omen'                 # (tools/factions.py's race)
DRONE, SWARM, SUPPORT = f'{MOD}:omen_drone', f'{MOD}:omen_bat_swarm', f'{MOD}:omen_support'
CIVILIAN = f'{MOD}:civilian_ship'
CHANCE = 25                          # % of the Chorus bars offering each (the remake's default is 35)
VOID_CRYSTALS = 164                  # (the remake's Void energy fuel: the Rite Energy Fragment's stand-in)
FRACTURES = 5                        # (the tree's "Closed fractures" up to 5)
MANIFEST_S = 60                      # ("Manifestation in": its whiteboard's 60 s)
TASK_S = 10                          # (MTAction_ProgressSubObjective ProgressTime 10)
NEAR_M = 150                         # a fracture closes within this (metres; the server checks every 0.25 s)
ZONE_UNITS = 4000                    # the progress zone: within this many game units of the ship (200 m)


def xyz(p): return f"{int(round(p[0]))} {int(round(p[1]))} {int(round(p[2]))}"


def radio(t, speaker): return {"type": "radio", "speaker": speaker, "text": t}


def start(title, subtitle, intro, extra_vars, purpose, speaker):
    """The opening: the station the visitor sat in, a quiet orbit (the mission's own ships only), the launch, no travel
    until it is over, the visitor's words and the title (as the GoF3 Ships mod's missions)."""
    variables = [{"name": "st", "value": -1}, {"name": "done", "value": 0}, {"name": "left", "value": 0}] + list(extra_vars)
    steps = [
        {"type": "set", "variable": "st", "value": "station"},
        {"type": "questorbit", "station": "{st}"},
        {"type": "objective", "text": "Launch from {stationname(st)} " + purpose, "station": "{st}"},
        {"type": "checkpoint", "name": "accepted"},
        {"type": "waituntil", "condition": "inorbit({st}) > 0"},
        {"type": "restrict", "what": "all"},
        {"type": "wait", "seconds": 3},
        {"type": "title", "title": title, "subtitle": subtitle, "seconds": 4},
    ] + [radio(t, speaker) for t in intro if t]
    return variables, steps


def fail(title):
    return [{"type": "set", "variable": "done", "value": "2"}, {"type": "timer", "stop": True}, {"type": "pickup", "action": "clear"},
            {"type": "waypoint"}, {"type": "restrict", "what": "off"}, {"type": "fail", "title": title}]


def finish(outro, speaker):
    return [{"type": "set", "variable": "done", "value": "1"}, {"type": "timer", "stop": True}, {"type": "pickup", "action": "clear"},
            {"type": "waypoint"}, {"type": "restrict", "what": "off"}, {"type": "questorbit", "station": "{st}", "on": False},
            {"type": "sound", "sound": "success"}] + ([radio(outro, speaker)] if outro else []) + [{"type": "complete"}]


def mission(title, offer, reward, variables, steps, client):
    return {"format": "gof2mission", "title": title, "kind": "mission", "offer": offer, "reward": reward, "client": client,
            "stations": [f'{MOD}:{s}' for s in STATIONS], "chance": CHANCE, "takers": "station",
            "variables": variables, "steps": steps}


def fractures(centre, seed=11):
    """FRACTURES points on a tilted ring round the manifestation (game units, the station's frame), far enough apart."""
    rng = random.Random(seed)
    out, tilt = [], rng.uniform(-0.5, 0.5)
    for i in range(FRACTURES):
        a = 2 * math.pi * i / FRACTURES + rng.uniform(-0.25, 0.25)
        r = rng.uniform(16000, 24000)
        out.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a) * math.sin(tilt) + rng.uniform(-3000, 3000),
                    centre[2] + r * math.sin(a) * math.cos(tilt)))
    return out


def manifestation():
    client = "terran Resistance scout"
    centre = (0, 3000, 70000)
    pts = fractures(centre)
    offer = ("A Faceless manifestation is forming out past the station. Its fractures are tearing space open around it: fly "
             "into each one and close it before the manifestation breaks through, then destroy whatever still gets out. "
             "There is a fragment of the Void in it for you, if you live.")
    intro = [f"Close all {FRACTURES} fractures before it breaks through. Fly straight into them."]
    variables, steps = start("FACELESS MANIFESTATION", "Stop the manifestation", intro, [{"name": "closed", "value": 0}],
                             "to the manifestation", client)
    # each fracture closes once the player flies into it (in any order)
    for i, p in enumerate(pts):
        name = f"Fracture {i + 1}"
        steps += [{"type": "pickup", "station": "{st}", "at": xyz(p), "name": name},
                  {"type": "on", "trigger": "near", "station": "{st}", "at": xyz(p), "radius": NEAR_M, "steps": [
                      {"type": "if", "condition": "done == 0", "then": [
                          {"type": "pickup", "action": "remove", "name": name},
                          {"type": "set", "variable": "closed", "value": "closed + 1"},
                          {"type": "sound", "sound": "info"},
                          {"type": "title", "subtitle": "Closed fractures: {closed}/" + str(FRACTURES), "seconds": 2}]}]}]
    steps += [{"type": "waypoint", "station": "{st}", "at": xyz(centre)},
              {"type": "objective", "text": f"Stop the manifestation: close the {FRACTURES} fractures", "station": "{st}"},
              # the first of them meets the player on the way (the tree's 20 s timer)
              {"type": "spawn", "ship": DRONE, "race": OMEN, "count": 2, "behaviour": "enemy", "name": "Faceless",
               "at": xyz((centre[0], centre[1] + 4000, centre[2] - 15000))},
              {"type": "set", "variable": "left", "value": str(MANIFEST_S)},
              {"type": "timer", "seconds": "left", "label": "Manifestation in:"},
              {"type": "every", "seconds": 1, "steps": [
                  {"type": "if", "condition": f"done == 0 and closed < {FRACTURES}", "then": [
                      {"type": "set", "variable": "left", "value": "left - 1"},
                      {"type": "if", "condition": "left <= 0", "then": fail("The manifestation broke through")}]}]},
              {"type": "waituntil", "condition": f"closed >= {FRACTURES}"},
              {"type": "timer", "stop": True},
              {"type": "sound", "sound": "alarm"},
              {"type": "title", "subtitle": "The manifestation collapses", "seconds": 3},
              # what still comes through as it collapses (ActorAmount 4)
              {"type": "spawn", "ship": DRONE, "race": OMEN, "count": 2, "behaviour": "enemy", "name": "Faceless", "at": xyz(centre)},
              {"type": "spawn", "ship": SWARM, "race": OMEN, "count": 1, "behaviour": "enemy", "name": "Faceless",
               "at": xyz((centre[0] + 3000, centre[1], centre[2]))},
              {"type": "spawn", "ship": SUPPORT, "race": OMEN, "count": 1, "behaviour": "enemy", "name": "Faceless",
               "at": xyz((centre[0] - 3000, centre[1], centre[2]))},
              {"type": "objective", "text": "Destroy the Faceless entities", "station": "{st}"},
              {"type": "waypoint"},
              {"type": "waituntil", "condition": 'alive("Faceless") > 0', "timeout": 10},
              {"type": "waituntil", "condition": 'alive("Faceless") == 0'},
              {"type": "reward", "items": [{"item": VOID_CRYSTALS, "amount": 5}], "title": "A fragment of the Void"}]
    steps += finish("It's gone. The Void will take a while to stitch itself back together.", client)
    return mission("Faceless Manifestation", offer, 24000, variables, steps, client)


TASKS = [  # (Chorus's objective line, the progress label)
    ("Transfer fuel to civilian ship", "Fuel transfer"),
    ("Counter hack the civilian ship's system", "Counter hacking"),
    ("Calibrate the civilian ship's systems", "Calibrating"),
]


def civilian():
    client = "terran Civilian captain"
    at = (6000, 1500, 45000)
    offer = ("One of our ships is stranded out past the station and the crew can't fix it alone. Fly out, see what they "
             "need and stay close while it's done. Nobody else will go.")
    variables, steps = start("CIVILIAN ASSISTANCE", "Distress Signal", ["Find the civilian ship and contact it."],
                             [{"name": "task", "value": 0}, {"name": "met", "value": 0}, {"name": "prog", "value": 0}],
                             "to the stranded ship", client)
    near = f"distance(player, {at[0]:.0f}, {at[1]:.0f}, {at[2]:.0f})"
    steps += [{"type": "set", "variable": "task", "value": f"random(1, {len(TASKS)})"},
              {"type": "spawn", "ship": CIVILIAN, "race": "terran", "count": 1, "behaviour": "friendly", "name": "Civilian Ship", "at": xyz(at)},
              {"type": "waituntil", "condition": 'alive("Civilian Ship") > 0', "timeout": 10},
              {"type": "shipaction", "ship": "Civilian Ship", "action": "hold"},
              {"type": "waypoint", "station": "{st}", "at": xyz(at)},
              {"type": "objective", "text": "Contact civilian ship", "station": "{st}"},
              {"type": "every", "seconds": 2, "steps": [
                  {"type": "if", "condition": 'done == 0 and alive("Civilian Ship") == 0', "then": fail("The civilian ship was destroyed")}]},
              {"type": "waituntil", "condition": f"{near} >= 0 and {near} <= {ZONE_UNITS * 2}"},
              {"type": "set", "variable": "met", "value": "1"},
              {"type": "sound", "sound": "info"}]
    for i, (line, label) in enumerate(TASKS):
        steps += [{"type": "if", "condition": f"task == {i + 1}", "then": [
            {"type": "objective", "text": line, "station": "{st}"},
            {"type": "title", "subtitle": f"{line}: stay within {ZONE_UNITS // 20} m for {TASK_S} s", "seconds": 4}]}]
    # the progress zone: a second for every second the player stays beside the ship
    labels = {i + 1: label for i, (_, label) in enumerate(TASKS)}
    steps += [{"type": "every", "seconds": 1, "steps": [
        {"type": "if", "condition": f"done == 0 and met == 1 and prog < {TASK_S} and {near} >= 0 and {near} <= {ZONE_UNITS}", "then": [
            {"type": "set", "variable": "prog", "value": "prog + 1"}]
            + [{"type": "if", "condition": f"task == {k}", "then": [
                {"type": "title", "subtitle": f"{v}: {{floor(prog * 100 / {TASK_S})}} %", "seconds": 1}]} for k, v in labels.items()]}]},
              {"type": "waituntil", "condition": f"prog >= {TASK_S}"},
              {"type": "sound", "sound": "success"},
              {"type": "title", "subtitle": "Civilian assistance: done", "seconds": 3},
              {"type": "shipaction", "ship": "Civilian Ship", "action": "jump"},
              {"type": "wait", "seconds": 3}]
    steps += finish("We're moving again. Thank you, pilot.", client)
    return mission("Civilian Assistance", offer, 9000, variables, steps, client)


MISSIONS = {'chorus_manifestation': manifestation, 'chorus_civilian': civilian}


def build(out, log=print):
    """Writes <out>/events/chorus_*.gof2mission. -> how many."""
    folder = os.path.join(out, 'events')
    os.makedirs(folder, exist_ok=True)
    for name, make in MISSIONS.items():
        json.dump(make(), open(os.path.join(folder, name + '.gof2mission'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    log(f"  missions: {len(MISSIONS)} bar missions (Chorus's encounters the remake had no counterpart for)")
    return len(MISSIONS)
