"""Chorus's two enemy factions as the remake's mod races (races.json, Modding/README "Races"), and Chorus's bosses in the
remake's rift runs (encounters.json "rift" "bosses", Modding/README "Encounters"):

- The Circle (the Great Prophet's order: its fighters, students, disruptors, gunships, warships, the Prophet, Sav, Ree and
  Aryana) and the Omen (the Faceless: drones, swarms, support, fortresses), both hostile. Their fighters fly for them as
  well as for the game's pirates and the Void (traffic "races": the GoF2 galaxy still meets them as before), their
  capital ships for them alone (npcships.json "race"); the Chorus systems name both as their raiders (tools/world.py).
  A rift stage can then be "the Circle's" or "the Omen's" (the remake picks among the hostile mod races with fighters).
- The rift's boss pool: the Omen's elite fortress and the Circle's dreadnought, destroyer and warship as capital bosses
  (they park and fire their turrets), the Omen fortress, the Prophet, Sav, Ree and Aryana as fighter bosses with
  Chorus's guns; in the Chorus systems the run looks like Chorus's Rift (its "look", tools/rift.py).
"""
MOD = 'chorus_ships'
CIRCLE_ID, OMEN_ID = f'{MOD}:circle', f'{MOD}:omen'
RACES = [
    {'id': 'circle', 'name': 'The Circle', 'look': 'pirates', 'hostile': True, 'color': [0.78, 0.1, 0.07],
     'description': "The Great Prophet's order, ruling the stars through fear: its fighters, gunships and warships (Chorus)."},
    {'id': 'omen', 'name': 'The Omen', 'look': 'void', 'hostile': True, 'color': [0.45, 0.22, 0.9],
     'description': 'The Faceless and their drones, swarms and fortresses, come through the rifts (Chorus).'},
]
CIRCLE = {'circle_fighter', 'circle_fighter_snipe', 'circle_fighter_net', 'student_fighter', 'circle_scout', 'circle_support',
          'circle_support_drone', 'disruptor', 'circle_gunship', 'circle_gunship_apex', 'circle_gunship_elite', 'student_gunship',
          'prophet', 'sav', 'ree', 'aryana', 'circle_warship', 'circle_destroyer', 'circle_dreadnought', 'dropship'}
OMEN = {'omen_drone', 'omen_bat_swarm', 'omen_support', 'omen_fortress', 'omen_fortress_elite'}
RAIDERS = [CIRCLE_ID, OMEN_ID]
# (ship, raiders' hulls, faction, gun, missiles): the rift's bosses
BOSSES = [
    ('omen_fortress_elite', 14, OMEN_ID, None, None),
    ('circle_dreadnought', 16, CIRCLE_ID, None, None),
    ('circle_destroyer', 12, CIRCLE_ID, None, None),
    ('circle_warship', 10, CIRCLE_ID, None, None),
    ('omen_fortress', 8, OMEN_ID, 'chorus_laser_t3a', 'chorus_missiles_t3a'),
    ('prophet', 10, CIRCLE_ID, 'chorus_laser_t3b', 'chorus_missiles_t3b'),
    ('sav', 7, CIRCLE_ID, 'chorus_gatling_t3a', 'chorus_missiles_t2a'),
    ('ree', 7, CIRCLE_ID, 'chorus_laser_t3a', 'chorus_missiles_t2b'),
    ('aryana', 8, CIRCLE_ID, 'chorus_gatling_t3b', 'chorus_missiles_t3a'),
]


def faction(sid):
    return CIRCLE_ID if sid in CIRCLE else OMEN_ID if sid in OMEN else None


def apply(enemies, capitals):
    """Adds the factions to the ships' traffic and the capital ships' npcships.json race (in place)."""
    for e in enemies:
        f, t = faction(e['id']), e.get('traffic')
        if f and isinstance(t, dict) and isinstance(t.get('races'), list) and f not in t['races']:
            t['races'] = t['races'] + [f]
    for c in capitals:
        f = faction(c['id'])
        if f: c['race'] = f; c['hostile'] = True


def rift(enemies, items, look=None):
    """encounters.json: the rift's Chorus bosses (those built, with the items that exist), and the Chorus systems' rift look
    (tools/rift.py) when built."""
    ships, guns = {e['id'] for e in enemies}, {i['id'] for i in items}
    bosses = []
    for sid, raiders, race, gun, missiles in BOSSES:
        if sid not in ships: continue
        b = {'ship': f'{MOD}:{sid}', 'raiders': raiders, 'race': race}
        if gun in guns: b['weapon'] = f'{MOD}:{gun}'
        if missiles in guns: b['secondary'] = f'{MOD}:{missiles}'
        bosses.append(b)
    if not bosses and not look: return []
    e = {'id': 'chorus_rift', 'kind': 'rift', 'bosses': bosses}
    if look: e['look'] = look
    return [e]
