import json
import random
import argparse
import re

tables = {}

def load_tables(filename):
    ts = {}
    with open(filename, "r") as f:
        ts = json.load(f)
    return ts

def parse_table_option(s):
    m = re.search("{(.*)}", s)
    # m[0] = {foo:bar}
    # m[1] = foo:bar
    if not m:
        # Literal string
        return s
    elif m[1].startswith("*"):
        # Special cases
        if m[1] == "*treasure":
            pass
        elif m[1] == "*npc":
            # TODO make actual NPC?
            return parse_table_option(s.replace(m[0], make_random_name()))
        elif m[1].startswith("*an"):
            parts = m[1].split(":")
            word = parse_table_option(f"{{{':'.join(parts[1:])}}}")
            if word and word[0] in "aeiou":
                article = "an"
            else:
                article = "a"
            return s.replace(m[0], f"{article} {word}")
        else:
            # Can't find this special case
            return s
    else:
        # Random table lookup, e.g. {characters:female names}
        refs = m[1].split(":")
        d = tables
        for r in refs:
            if r in d:
                d = d[r]
            else:
                # Table doesn't exist
                return s
        # If we get to this point, d should be a list of strings.
        # Careful -- this could recurse.
        if not d:
            print(f"bad parse expression: {s}")
        return parse_table_option(s.replace(m[0], random.choice(d)))

def make_character(character_level=1):
    c = {}
    c["NOTES"] = []
    c["SPELL SLOTS"] = 0
    c["SPELLS"] = []
    c["PATHS"] = []
    c["ATTACK"] = 0
    c["ARMOR"] = 6
    c["BACKPACK"] = []
    c["WORN"] = []
    c["BELT"] = []
    c["HANDS"] = []
    # Roll or choose abilities
    scores = random.choice(tables["abilities"]["abilities"])
    ability_names = tables["abilities"]["ability names"]
    for ability, score in zip(ability_names, scores):
        c[ability] = score
    # Record maximum health (gain_a_level ups this to 4)
    c["MAX HEALTH"] = 2
    c["HEALTH"] = 2
    # Choose starting feature
    c["XP"] = 0
    c["LEVEL"] = 0
    for i in range(character_level):
        gain_a_level(c) # Grants a random new feature at LVL 1
    # Choose six items
    for i in range(6):
        # Duplicates are fine; every item takes a different slot.
        c["BACKPACK"].append(parse_table_option("{items:items}"))
    # Choose combat gear
    grant_armor(c, "light armor")
    grant_armor(c, "shield")
    for i in range(2):
        category = random.choice(
            list(tables["items"]["weapons"].keys()))
        grant_weapon(c, category)
    # Choose background and appearance
    # (Adventurer's gender has been ignored for convenience, but this can
    # lead to situations like female adventurers wearing a mustache or male
    # adventurers wearing haute couture. This is fine. Players can, of
    # course, reroll any of these traits or choose their own.)
    for (table_name, caption) in [
        ("appearances",            "Appearance:      "),
        ("physical details",       "Physical detail: "),
        ("underworld professions", "Background:      "),
        ("personalities",          "Personality:     "),
        ("mannerisms",             "Mannerism:       ")
    ]:
        var = parse_table_option(f"{{characters:{table_name}}}")
        c["NOTES"].append(f"{caption}{cfl(var)}")
    # Clothes are always worn, sometimes under armor
    clothing = parse_table_option("{characters:clothing}")
    c["WORN"].append(f"clothes ({clothing})")
    # Set up spells
    while len(c["SPELLS"]) < c["SPELL SLOTS"]:
        c["SPELLS"].append(make_random_spell())
    # Record name, level and XP
    c["NAME"] = make_random_name()
    # (Level and XP calculated above)
    return c

def format_character_sheet(c):
    left_panel = f"""
{c["NAME"]} (LVL {c["LEVEL"]} / {c["XP"]} XP)
STR +{c["STR"]}  ATTACK +{c["ATTACK"]}
DEX +{c["DEX"]}  ARMOR  {"{:2}".format(c["ARMOR"])}
WIL +{c["WIL"]}  HEALTH {"{:2}".format(c["HEALTH"])} ({c["MAX HEALTH"]})
"""
    for spell in c["SPELLS"]:
        left_panel += f"SPELL: {spell}\n"
    notes_panel = "\n".join(c["NOTES"])
    equipment_panel = "\n".join([
        "HANDS: " + ", ".join(c["HANDS"]),
        "BELT:  " + ", ".join(c["BELT"]),
        "WORN:  " + ", ".join(c["WORN"]),
        "BACKPACK:\n" + "\n".join(sorted(c["BACKPACK"]))
    ])
    return ("\n===\n".join([
        left_panel.strip(),
        notes_panel.strip(),
        equipment_panel.strip()]))

def format_npc(n):
    notes = "\n".join(["{:<16} {}".format(a + ":", b) for a, b in [
        ("Asset",           cfl(n["asset"])),
        ("Liability",       cfl(n["liability"])),
        ("Appearance",      cfl(n["appearance"])),
        ("Physical detail", cfl(n["physical detail"])),
        ("Personality",     cfl(n["personality"])),
        ("Goal",            cfl(n["goal"]))
    ]])
    return f"""
{n["name"]}, the {n["profession"]}.
{notes}
""".strip()

def cfl(s):
    # Capitalize first letter only
    if s:
        s = s[0].upper() + s[1:]
    return s

def apply_bonus(character, feature):
    # Returns whether feature was successfully applied
    tokens = feature.split()
    if tokens[0] == "bonus":
        size = int(tokens[1])
        stat = " ".join(tokens[2:])
        character[stat] += size
        return True
    elif tokens[0] == "path":
        all_paths = tables["abilities"]["paths"]
        if len(character["PATHS"]) >= len(all_paths):
            return False # Can't gain a new path
        available_paths = set(all_paths.keys()) - set(character["PATHS"])
        path, skills = random.choice([(p,s) for p,s in all_paths.items() if p in available_paths])
        path_description = f"{path.title()} (advantage on danger rolls related to {', '.join(skills)})"
        character["PATHS"].append(path)
        character["NOTES"].append(path_description)
        return True
    else:
        return False

def grant_armor(character, armor):
    new_armor = tables["items"]["armor"][armor]
    current_armor = None
    for worn_item in character[new_armor["slot"]]:
        if worn_item in tables["items"]["armor"]:
            current_armor = tables["items"]["armor"][worn_item]
            break
    if not current_armor:
        # Put on armor
        character[new_armor["slot"]].append(armor)
        character["ARMOR"] += new_armor["bonus"]
        return True
    elif new_armor["bonus"] > current_armor["bonus"]:
        # Swap armor
        character[new_armor["slot"]].remove(worn_item)
        character["ARMOR"] -= current_armor["bonus"]
        character["BACKPACK"].append(worn_item)
        character[new_armor["slot"]].append(armor)
        character["ARMOR"] += new_armor["bonus"]
        return True
    else:
        # Stash armor
        character["BACKPACK"].append(armor)
        return True

def grant_weapon(character, weapon_category):
    weapon = random.choice(tables["items"]["weapon names"][weapon_category])
    weapon_data = tables["items"]["weapons"][weapon_category]
    weapon_desc = f"{weapon} ({weapon_category})"
    if not character["HANDS"]:
        character["HANDS"].append(weapon_desc)
        return True
    elif character["HANDS"] == ["shield"]:
        if weapon_data["hands"] == 2:
            # 2H weapon replaces shield
            unequip(character, "shield")
            character["HANDS"].append(weapon_desc)
            return True
        elif weapon_data["hands"] == 1:
            # 1H weapon complements shield
            character["HANDS"].append(weapon_desc)
            return True
    # Try the belt, if there's room
    elif len(character["BELT"]) < 2:
        character["BELT"].append(weapon_desc)
        return True
    else:
        character["BACKPACK"].append(weapon_desc)
        return True

def unequip(character, item):
    # Moves the given item from hands to belt or backpack
    if item not in character["HANDS"]:
        return False
    else:
        character["HANDS"].remove(item)
        if item == "shield":
            # Right now, "shield" is the only object that improves armor
            # when held in hands
            character["ARMOR"] -= 1
        if len(character["BELT"]) < 2:
            character["BELT"].append(item)
            return True
        else:
            character["BACKPACK"].append(item)
            return True

def gain_a_level(c):
    new_level = c["LEVEL"] + 1
    c["LEVEL"] = new_level
    c["XP"] = new_level*(new_level - 1) # Minimum XP required to gain this level
    apply_bonus(c, "bonus 2 MAX HEALTH")
    c["HEALTH"] = c["MAX HEALTH"] # Assume level-up happens in a safe place
    if new_level % 2 == 1:
        # Can't gain the same path more than once
        for tries in range(100):
            feature = parse_table_option("{abilities:features}")
            if apply_bonus(c, feature):
                break
        if tries == 99:
            print("Warning: no bonus from reaching LVL {new_level}.")
    else:
        ability = parse_table_option("{abilities:ability names}")
        apply_bonus(c, f"bonus 1 {ability}")
    pass

def make_npc():
    npc = {}
    npc["name"] = make_random_name()
    npc["type"] = random.choice(["civilized",  "underworld", "wilderness"])
    npc["profession"] = parse_table_option(f"{{characters:{npc['type']} professions}}")
    for key, s in [
        ("asset",           "{characters:assets}"),
        ("liability",       "{characters:liabilities}"),
        ("goal",            "{characters:npc goals}"),
        ("appearance",      "{characters:appearances}"),
        ("physical detail", "{characters:physical details}"),
        ("clothing",        "{characters:clothing}"),
        ("personality",     "{characters:personalities}"),
        ("mannerism",       "{characters:mannerisms}")
    ]:
        npc[key] = parse_table_option(s)
    return npc

def make_random_name():
    # Assume most adventurers (4 in 6) are male
    # (This seems consistent with pulp fantasy)
    gender = random.choices(["male", "female"], (4, 2)).pop()
    firstname = parse_table_option(f"{{characters:{gender} names}}")
    # Assume most adventurers (4 in 6) have lower class surnames
    # (This seems consistent with pulp fantasy)
    society = random.choices(["lower class", "upper class"], (4, 2)).pop()
    if society == "upper class" and random.randint(1, 36) == 1:
        # "This table can also be used for upper-class first names,
        #  if you want them to sound extra snobby."
        firstname = parse_table_option("{characters:upper class surnames}")
    surname = parse_table_option(f"{{characters:{society} surnames}}")
    return f"{firstname} {surname}".title()

def make_random_spell():
    category = parse_table_option("{magic:categories}")
    first_table, second_table = category.split(", ")
    first_word = random.choice(tables["magic"][first_table])
    second_word = random.choice(tables["magic"][second_table])
    return f"{first_word} {second_word}".title()

def do_menu(character_level=1):
    options = [
    #   (letter, description, function, return code)
    #   A return code of False ends the loop.
        ("a", "Generate random character",
            (lambda:format_character_sheet(make_character(character_level))), True),
        ("b", "Generate random name",
            (lambda:make_random_name()), True),
        ("c", "Generate random spell",
            (lambda:make_random_spell()), True),
        ("d", "Generate random npc",
            (lambda:format_npc(make_npc())), True),
        ("q", "Quit",
            (lambda:None), False)]
    for t in options:
        print(f"{t[0]}) {t[1]}")
    choice = input("> ")
    for t in options:
        if choice.lower() == t[0]:
            result = t[2]()
            if result:
                print(f"\n{result}\n")
            return t[3]
    print(f"Sorry, I don't understand \"{choice}\".")
    return True

def main():
    global tables
    tables["abilities"] = load_tables("./tables-abilities.json")
    tables["characters"] = load_tables("./tables-characters.json")
    tables["items"] = load_tables("./tables-items.json")
    tables["magic"] = load_tables("./tables-magic.json")

    parser = argparse.ArgumentParser()
    parser.add_argument("-c",
        dest="characters",
        nargs=1,
        default=["0"],
        help="number of complete characters to generate")
    parser.add_argument("-l",
        dest="level",
        nargs=1,
        default=["1"],
        help="level of generated characters (default 1)")
    parser.add_argument("-n",
        dest="names",
        nargs=1,
        default=["0"],
        help="number of names to generate")
    parser.add_argument("-s",
        dest="spells",
        nargs=1,
        default=["0"],
        help="number of spells to generate")
    parser.add_argument("-N",
        dest="npcs",
        nargs=1,
        default=["0"],
        help="number of NPCs to generate")
    args = parser.parse_args()
    characters = abs(int(args.characters[0]))
    level = abs(int(args.level[0]))
    names = abs(int(args.names[0]))
    spells = abs(int(args.spells[0]))
    npcs = abs(int(args.npcs[0]))

    if characters + names + spells + npcs == 0:
        # Interactive mode
        while do_menu(level):
            pass
    else:
        # Batch mode
        for i in range(characters):
            print(format_character_sheet(make_character(level)))
            print()
        for i in range(names):
            print(make_random_name())
        for i in range(spells):
            print(make_random_spell())
        for i in range(npcs):
            print(format_npc(make_npc()))
            print()
    return

if __name__ == "__main__":
    main()
