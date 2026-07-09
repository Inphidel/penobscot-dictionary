#!/usr/bin/env python3
"""Mine semantic theme tags from English glosses for Lab relatedness.

Tags are experimental Lab metadata — not official dictionary categories.
Precision over recall: prefer clear lemmas and phrases over bare stop-prone words.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict

from common import (
    ENGLISH_INDEX_JSON,
    ENTRIES_JSON,
    SEMANTIC_TAGS_JSON,
    ensure_dirs,
    load_json,
    save_json,
)

# ---------------------------------------------------------------------------
# Taxonomy: groups + tags
# Each tag: id, label, group, specificity (theme|lemma|meta), optional parent,
# english_patterns (regex), optional exclude_patterns, optional keywords (Lab query),
# confidence when matched (high|medium|low).
# ---------------------------------------------------------------------------

GROUPS = [
    {"id": "animals", "label": "Animals", "description": "Animals, birds, fish, insects, and related words"},
    {"id": "plants", "label": "Plants & trees", "description": "Trees, plants, berries, and plant materials"},
    {"id": "body", "label": "Body", "description": "Body parts and bodily features"},
    {"id": "nature", "label": "Nature & landscape", "description": "Water, weather, landforms, fire, stone"},
    {"id": "objects", "label": "Objects & tools", "description": "Tools, craft items, dwellings, boats"},
    {"id": "food", "label": "Food & cooking", "description": "Food, cooking, hunger, drink"},
    {"id": "people", "label": "People & social", "description": "People, roles, health, life and death"},
    {
        "id": "survival",
        "label": "Survival & action",
        "description": "Hide, find, track, hurt, defend, flee, pretend — life-skill / root-meaning clusters",
    },
    {"id": "motion", "label": "Motion & posture", "description": "Movement, posture, carrying"},
    {"id": "perception", "label": "Perception & speech", "description": "Sensing, thinking, speaking, arts"},
    {"id": "meta", "label": "Dictionary markers", "description": "Structural gloss markers (species names, place names)"},
]


def _lemma(tag_id: str, label: str, group: str, words: list[str], *, parent: str | None = None,
           extra_patterns: list[str] | None = None, exclude: list[str] | None = None,
           headword_patterns: list[str] | None = None,
           confidence: str = "medium", description: str | None = None) -> dict:
    """Build a lemma tag from whole-word keywords plus optional extra patterns."""
    pats = [rf"\b{re.escape(w)}\b" for w in words]
    if extra_patterns:
        pats.extend(extra_patterns)
    return {
        "id": tag_id,
        "label": label,
        "group": group,
        "specificity": "lemma",
        "parent": parent,
        "description": description or f"Glosses that mention {label.lower()}",
        "english_patterns": pats,
        "exclude_patterns": exclude or [],
        "headword_patterns": headword_patterns or [],
        "keywords": words,
        "confidence": confidence,
    }


def _theme(tag_id: str, label: str, group: str, patterns: list[str], *,
           keywords: list[str] | None = None, exclude: list[str] | None = None,
           headword_patterns: list[str] | None = None,
           confidence: str = "medium", description: str | None = None) -> dict:
    return {
        "id": tag_id,
        "label": label,
        "group": group,
        "specificity": "theme",
        "parent": None,
        "description": description or f"Theme: {label.lower()}",
        "english_patterns": patterns,
        "exclude_patterns": exclude or [],
        "headword_patterns": headword_patterns or [],
        "keywords": keywords or [],
        "confidence": confidence,
    }


def _meta(tag_id: str, label: str, patterns: list[str], *, keywords: list[str] | None = None,
          headword_patterns: list[str] | None = None,
          description: str | None = None) -> dict:
    return {
        "id": tag_id,
        "label": label,
        "group": "meta",
        "specificity": "meta",
        "parent": None,
        "description": description or label,
        "english_patterns": patterns,
        "exclude_patterns": [],
        "headword_patterns": headword_patterns or [],
        "keywords": keywords or [],
        "confidence": "high",
    }


TAGS: list[dict] = [
    # --- Meta (high precision structural) ---
    _meta(
        "species",
        "Scientific name (species)",
        [r"⟨sciname⟩", r"<sciname>", r"\bsciname\b"],
        keywords=["sciname"],
        description="Gloss includes a scientific (Latin) species name marker",
    ),
    _meta(
        "place_name",
        "Place name",
        [r"_PN_", r"\bplace name\b", r"\bplacename\b"],
        keywords=["placename"],
        description="Gloss marked as a place name",
    ),
    _meta(
        "loanword",
        "Loanword",
        [r"\bloan from\b", r"\bloanword\b", r"\[loan"],
        keywords=["loan"],
        description="Marked as a loan from another language",
    ),

    # --- Animals: themes ---
    _theme(
        "animal",
        "Animal (general)",
        "animals",
        [r"\banimal\b", r"\banimals\b", r"\bbeast\b", r"\bcreature\b"],
        keywords=["animal", "animals", "beast", "creature"],
        description="General animal vocabulary",
    ),
    _theme(
        "bird",
        "Bird",
        "animals",
        [r"\bbird\b", r"\bbirds\b", r"\bfowl\b"],
        keywords=["bird", "birds", "fowl"],
    ),
    _theme(
        "fish_theme",
        "Fish",
        "animals",
        [r"\bfish\b", r"\bfishes\b", r"\bfishing\b"],
        keywords=["fish", "fishes", "fishing"],
        description="Fish and fishing-related glosses",
    ),
    _theme(
        "insect",
        "Insect / bug",
        "animals",
        [r"\binsect\b", r"\bbug\b", r"\bfly\b(?!\s+open)", r"\bbee\b", r"\bant\b", r"\blouse\b", r"\bflea\b", r"\bworm\b", r"\bdragonfly\b", r"\bmosquito\b"],
        keywords=["insect", "bug", "bee", "ant", "louse", "flea", "worm", "dragonfly", "mosquito"],
    ),

    # --- Animals: lemmas ---
    _lemma("bear", "Bear", "animals", ["bear", "bears", "cub"], parent="animal",
           exclude=[r"\bbear\s+(fruit|witness|in\s+mind|the\s+brunt|up\s+under|down\s+on|with\s+him)"]),
    _lemma("moose", "Moose", "animals", ["moose"], parent="animal"),
    _lemma("deer", "Deer", "animals", ["deer", "fawn", "buck", "doe", "venison"], parent="animal",
           exclude=[r"\bbuck\s+(up|skin\s+knife)"]),
    _lemma("beaver", "Beaver", "animals", ["beaver", "beavers"], parent="animal"),
    _lemma("seal", "Seal", "animals", ["seal", "seals"], parent="animal",
           exclude=[r"\bseal\s+(up|off|the|with)\b", r"\bsealed\b"]),
    _lemma("dog", "Dog", "animals", ["dog", "dogs", "puppy", "puppies"], parent="animal"),
    _lemma("wolf", "Wolf", "animals", ["wolf", "wolves"], parent="animal"),
    _lemma("fox", "Fox", "animals", ["fox", "foxes"], parent="animal"),
    _lemma("rabbit", "Rabbit / hare", "animals", ["rabbit", "rabbits", "hare", "hares"], parent="animal"),
    _lemma("squirrel", "Squirrel", "animals", ["squirrel", "squirrels"], parent="animal"),
    _lemma("otter", "Otter", "animals", ["otter", "otters"], parent="animal"),
    _lemma("porcupine", "Porcupine", "animals", ["porcupine", "porcupines"], parent="animal"),
    _lemma("turtle", "Turtle", "animals", ["turtle", "turtles", "tortoise"], parent="animal"),
    _lemma("snake", "Snake", "animals", ["snake", "snakes", "serpent"], parent="animal"),
    _lemma("frog", "Frog / toad", "animals", ["frog", "frogs", "toad", "toads", "treefrog"], parent="animal"),
    # "eagle" alone never appears in glosses — cover real birds of prey found in archive
    _lemma(
        "eagle",
        "Eagle / osprey / raptor",
        "animals",
        ["eagle", "eagles", "osprey", "ospreys", "fishhawk", "fishhawks", "gyrfalcon", "raptor"],
        parent="bird",
        extra_patterns=[r"\bfish\s*hawks?\b", r"\bbald\s+eagle\b", r"\bgolden\s+eagle\b"],
    ),
    _lemma("owl", "Owl", "animals", ["owl", "owls", "screech-owl", "horned owl"], parent="bird",
           extra_patterns=[r"\bbarred\s+owl\b", r"\bboreal\s+owl\b", r"\bscreech\s*owl\b"]),
    _lemma("duck", "Duck", "animals", ["duck", "ducks", "mallard", "teal", "whistler"], parent="bird",
           exclude=[r"\bduck\s+(down|under|into|out)\b", r"\bducking\b"]),
    _lemma("goose", "Goose", "animals", ["goose", "geese", "gander"], parent="bird",
           exclude=[r"\bgoose\s+(pimple|flesh|bump|pimples)"]),
    _lemma("crow", "Crow / raven", "animals", ["crow", "crows", "raven", "ravens", "corvus"], parent="bird"),
    _lemma("salmon", "Salmon", "animals", ["salmon", "anadromous"], parent="fish_theme",
           extra_patterns=[r"\batlantic\s+salmon\b"]),
    _lemma("trout", "Trout", "animals", ["trout", "char", "charr"], parent="fish_theme",
           extra_patterns=[r"\blake\s+trout\b", r"\bblueback\s+trout\b"]),
    _lemma("eel", "Eel", "animals", ["eel", "eels", "lamprey"], parent="fish_theme"),
    _lemma("whale", "Whale", "animals", ["whale", "whales", "orca", "porpoise", "dolphin"], parent="animal"),
    _lemma("muskrat", "Muskrat", "animals", ["muskrat", "muskrats"], parent="animal"),
    _lemma("mink", "Mink", "animals", ["mink", "minks", "mustela"], parent="animal"),
    _lemma("lynx", "Lynx / cat", "animals", ["lynx", "bobcat", "wildcat", "cougar", "panther"], parent="animal",
           extra_patterns=[r"\bcat\b(?!\s+tail)"], exclude=[r"\bcatch\b", r"\bcatalog\b", r"\bcattle\b"]),
    _lemma("partridge", "Partridge / grouse", "animals", ["partridge", "grouse", "ptarmigan"], parent="bird"),
    _lemma("heron", "Heron", "animals", ["heron", "herons", "bittern", "egret", "crane"], parent="bird",
           exclude=[r"\bcrane\s+(up|over|one's)\b"]),
    _lemma("hawk", "Hawk / falcon", "animals", ["hawk", "hawks", "falcon", "falcons", "buteo", "kestrel"], parent="bird"),
    _lemma("caribou", "Caribou / elk", "animals", ["caribou", "elk", "bison", "buffalo"], parent="animal"),
    _lemma("weasel", "Weasel / skunk", "animals", ["weasel", "weasels", "skunk", "skunks", "ermine"], parent="animal"),
    _lemma("shellfish", "Shellfish / crustacean", "animals", ["clam", "clams", "oyster", "oysters", "lobster", "crab", "crabs", "mussel", "shellfish"], parent="animal"),

    # --- Plants ---
    _theme(
        "tree",
        "Tree",
        "plants",
        [r"\btree\b", r"\btrees\b", r"\bwood\b", r"\btimber\b", r"\blog\b"],
        keywords=["tree", "trees", "wood", "timber"],
        exclude=[r"\bwould\b", r"\bwoodchuck\b"],
    ),
    _theme(
        "plant",
        "Plant",
        "plants",
        [r"\bplant\b", r"\bplants\b", r"\bherb\b", r"\bweed\b", r"\broot\b(?!\s+word)"],
        keywords=["plant", "plants", "herb", "weed"],
    ),
    _lemma("berry", "Berry", "plants", ["berry", "berries"], parent="plant"),
    _lemma("maple", "Maple", "plants", ["maple"], parent="tree"),
    _lemma("birch", "Birch", "plants", ["birch"], parent="tree"),
    _lemma("cedar", "Cedar", "plants", ["cedar"], parent="tree"),
    _lemma("pine", "Pine", "plants", ["pine", "pines"], parent="tree",
           exclude=[r"\bpine\s+for\b", r"\bpining\b"]),
    _lemma("ash_tree", "Ash (tree)", "plants", ["ash"], parent="tree",
           extra_patterns=[r"\bash\s+tree\b", r"\bwhite\s+ash\b", r"\bblack\s+ash\b"],
           exclude=[r"\bash\s+(es|tray|amed)\b", r"\bashes\b", r"\bcigarette\b"]),
    _lemma("spruce", "Spruce / fir / balsam", "plants", ["spruce", "balsam", "fir", "firs", "hemlock"], parent="tree"),
    _lemma("willow", "Willow / alder", "plants", ["willow", "willows", "alder", "alders"], parent="tree"),

    # --- Body ---
    _lemma("hand", "Hand", "body", ["hand", "hands", "finger", "fingers", "thumb", "palm"], parent=None),
    _lemma("head", "Head", "body", ["head", "heads", "skull", "forehead", "scalp"], parent=None,
           exclude=[r"\bhead\s+(for|toward|off|of\s+the|man|water|start)\b", r"\bheading\b", r"\bheadway\b"]),
    _lemma("eye", "Eye", "body", ["eye", "eyes", "eyelid", "eyebrow"], parent=None),
    _lemma("ear", "Ear", "body", ["ear", "ears"], parent=None,
           exclude=[r"\bearly\b", r"\bearn\b", r"\bearth\b"]),
    _lemma("nose", "Nose", "body", ["nose", "noses", "nostril"], parent=None),
    _lemma("mouth", "Mouth", "body", ["mouth", "mouths", "lip", "lips", "tongue"], parent=None),
    _lemma("tooth", "Tooth", "body", ["tooth", "teeth"], parent=None),
    _lemma("hair", "Hair", "body", ["hair", "hairs", "beard", "whisker"], parent=None),
    _lemma("skin", "Skin", "body", ["skin", "skins", "hide", "pelt"], parent=None,
           exclude=[r"\bhide\s+(from|behind|away|out)\b", r"\bhiding\b"]),
    _lemma("bone", "Bone", "body", ["bone", "bones"], parent=None),
    _lemma("blood", "Blood", "body", ["blood", "bloody"], parent=None),
    _lemma("foot", "Foot / leg", "body", ["foot", "feet", "leg", "legs", "knee", "ankle", "toe", "toes"], parent=None),
    _lemma("arm", "Arm / shoulder", "body", ["arm", "arms", "shoulder", "elbow", "wrist"], parent=None,
           exclude=[r"\barm\s+(of\s+the\s+sea|chair)\b", r"\barmed\b", r"\barmy\b"]),
    _lemma("heart", "Heart", "body", ["heart", "hearts", "heartbeat", "palpitation"], parent=None),
    _lemma("belly", "Belly / stomach", "body", ["belly", "stomach", "abdomen", "gut"], parent=None),
    _lemma("back_body", "Back (body)", "body", ["backbone", "spine"], parent=None,
           extra_patterns=[r"\bhis\s+back\b", r"\bher\s+back\b", r"\bmy\s+back\b", r"\bon\s+the\s+back\b", r"\bback\s+of\s+(the\s+)?(hand|neck|head)"]),
    _lemma("neck", "Neck / throat", "body", ["neck", "throat"], parent=None),
    _lemma("face", "Face", "body", ["face", "faces", "cheek", "cheeks", "chin", "forehead", "jaw"], parent=None,
           exclude=[r"\bface\s+(to\s+face|value|up\s+to)\b", r"\bfacing\b"]),

    # --- Nature ---
    _theme(
        "water",
        "Water",
        "nature",
        [
            r"\bwater\b",
            r"\bwaters\b",
            r"\baquatic\b",
            r"\bstream\b",
            r"\bcreek\b",
            r"\bbrook\b",
        ],
        keywords=["water", "waters", "stream", "creek", "brook"],
        exclude=[r"\bwater\s+down\b"],
        confidence="medium",
        description="Water and small waterways (noisy on verbs — verify)",
    ),
    _lemma("river", "River", "nature", ["river", "rivers"], parent="water"),
    _lemma("lake", "Lake", "nature", ["lake", "lakes", "pond", "ponds"], parent="water"),
    _lemma("snow", "Snow", "nature", ["snow", "snowy", "snowshoe", "snowshoes"], parent=None),
    _lemma("ice", "Ice", "nature", ["ice", "icy", "frozen"], parent=None,
           exclude=[r"\bice\s+cream\b"]),
    _lemma("wind", "Wind", "nature", ["wind", "winds", "windy", "breeze", "gale"], parent=None,
           exclude=[r"\bwind\s+up\b", r"\bwinding\b", r"\bwinded\b"]),
    _lemma("rain", "Rain", "nature", ["rain", "rains", "rainy", "rainfall"], parent=None),
    _lemma("fire", "Fire", "nature", ["fire", "fires", "flame", "flames", "blaze", "ember"], parent=None,
           exclude=[r"\bfire\s+(off|away|at|upon)\b", r"\bfired\b", r"\bfirearm\b"]),
    _lemma("stone", "Stone / rock", "nature", ["stone", "stones", "rock", "rocks", "pebble"], parent=None,
           exclude=[r"\brock\s+(back|the\s+cradle)\b", r"\brocking\b"]),
    _lemma("earth", "Earth / ground", "nature", ["earth", "ground", "soil", "dirt", "mud"], parent=None,
           exclude=[r"\bground\s+(up|into|meat|corn)\b", r"\bgroundhog\b"]),
    _lemma("mountain", "Mountain / hill", "nature", ["mountain", "mountains", "hill", "hills", "ridge"], parent=None),
    _lemma("sky", "Sky / cloud", "nature", ["sky", "skies", "cloud", "clouds", "heaven"], parent=None),
    _lemma("sun", "Sun", "nature", ["sun", "sunny", "sunshine", "sunrise", "sunset"], parent=None),
    _lemma("moon", "Moon", "nature", ["moon", "moonlight", "lunar"], parent=None),
    _lemma("star", "Star", "nature", ["star", "stars", "stellar"], parent=None,
           exclude=[r"\bstar\s+(in|as|of\s+the\s+show)\b", r"\bstarring\b", r"\bstarvation\b", r"\bstare\b"]),
    _lemma("thunder", "Thunder / lightning", "nature", ["thunder", "lightning", "thunderstorm"], parent=None),
    _lemma("island", "Island", "nature", ["island", "islands"], parent=None),
    _lemma("forest", "Forest / woods", "nature", ["forest", "forests", "woods", "woodland"], parent=None),
    _lemma("land", "Land / country", "nature", ["land", "lands", "country", "territory", "shore", "shores", "coast"], parent=None,
           exclude=[r"\bland\s+(on|upon|a\s+blow)\b", r"\blanding\b", r"\bcountryside\b"]),
    _lemma("night", "Night / day", "nature", ["night", "nights", "nighttime", "daytime", "dawn", "dusk", "evening", "morning"], parent=None,
           extra_patterns=[r"\bby\s+day\b", r"\bby\s+night\b", r"\ball\s+day\b", r"\ball\s+night\b"]),
    _lemma("cold", "Cold / freeze", "nature", ["cold", "colder", "chill", "chilly", "freeze", "freezing", "frost", "frosty"], parent=None),
    _lemma("warm", "Warm / heat", "nature", ["warm", "warmer", "heat", "hot", "heated", "lukewarm"], parent=None,
           exclude=[r"\bhot\s+(tempered|headed)\b"]),
    _lemma("light", "Light / bright", "nature", ["light", "lights", "bright", "brightness", "shine", "shines", "shining", "glow", "glowing", "illuminate"], parent=None,
           exclude=[r"\blight\s+(up\s+a\s+cigarette|weight|hearted)\b", r"\blighter\b", r"\blightning\b"]),
    _lemma("sound", "Sound / noise", "nature", ["sound", "sounds", "noise", "noisy", "loud", "quiet", "silent", "silence"], parent=None,
           exclude=[r"\bsound\s+(asleep|as\s+a)\b"]),

    # --- Objects ---
    _lemma("canoe", "Canoe", "objects", ["canoe", "canoes", "boat", "boats"], parent=None),
    _lemma("paddle", "Paddle", "objects", ["paddle", "paddles", "paddling"], parent="canoe"),
    _lemma("house", "House / dwelling", "objects", ["house", "houses", "home", "dwelling", "wigwam", "lodge", "camp"], parent=None,
           exclude=[r"\bhome\s+(to|in\s+on)\b", r"\bhoming\b"]),
    _lemma("knife", "Knife", "objects", ["knife", "knives", "blade"], parent=None),
    _lemma("basket", "Basket", "objects", ["basket", "baskets"], parent=None),
    _lemma("bow_arrow", "Bow & arrow", "objects", ["bow", "bows", "arrow", "arrows", "quiver"], parent=None,
           exclude=[r"\bbow\s+(down|one's|his|her|the\s+head)\b", r"\bbowing\b", r"\bbowed\b"]),
    _lemma("net", "Net", "objects", ["net", "nets", "snare", "snares"], parent=None),
    _lemma("trap", "Trap", "objects", ["trap", "traps", "trapping"], parent=None,
           exclude=[r"\btrap\s+door\b"]),
    _lemma("drum", "Drum", "objects", ["drum", "drums", "drumming"], parent=None),
    _lemma("pipe", "Pipe", "objects", ["pipe", "pipes", "tobacco"], parent=None),
    _lemma("axe", "Axe / hatchet", "objects", ["axe", "ax", "hatchet"], parent=None),
    _lemma("spear", "Spear", "objects", ["spear", "spears", "harpoon"], parent=None),
    _lemma("rope", "Rope / string", "objects", ["rope", "ropes", "string", "cord", "thong"], parent=None),
    _lemma("pot", "Pot / kettle", "objects", ["pot", "pots", "kettle", "kettles", "pail"], parent=None),
    _lemma("moccasin", "Moccasin / shoe", "objects", ["moccasin", "moccasins", "shoe", "shoes"], parent=None),
    _lemma("snowshoe_obj", "Snowshoe", "objects", ["snowshoe", "snowshoes"], parent=None),
    _lemma("blanket", "Blanket / cloth", "objects", ["blanket", "blankets", "cloth", "fabric", "robe"], parent=None),
    _lemma("door", "Door", "objects", ["door", "doors", "doorway", "entrance"], parent=None),
    _lemma("tobacco", "Tobacco / smoke", "objects", ["tobacco", "smoke", "smoking", "smokes", "smoked", "cigar", "pipe tobacco"], parent=None,
           exclude=[r"\bsmoke\s+signal\b"]),
    _lemma("bead", "Bead / quillwork", "objects", ["bead", "beads", "beading", "quill", "quills", "wampum"], parent=None),

    # --- Food ---
    _theme(
        "food",
        "Food",
        "food",
        [r"\bfood\b", r"\bmeal\b", r"\bfeast\b", r"\beat\b", r"\beating\b", r"\beaten\b", r"\bhungry\b", r"\bhunger\b"],
        keywords=["food", "meal", "feast", "eat", "hungry", "hunger"],
    ),
    _lemma("meat", "Meat", "food", ["meat", "flesh", "venison"], parent="food"),
    _lemma("cook", "Cook / boil", "food", ["cook", "cooking", "cooked", "boil", "boiling", "boiled", "roast", "roasting", "bake", "baking"], parent="food"),
    _lemma("drink", "Drink", "food", ["drink", "drinks", "drinking", "thirst", "thirsty", "beverage"], parent="food"),
    _lemma("bread", "Bread", "food", ["bread", "loaf", "cake"], parent="food"),
    _lemma("maple_sugar", "Maple sugar", "food", ["maple sugar", "sugar", "syrup"], parent="food",
           extra_patterns=[r"\bmaple\s+sugar\b", r"\bsugar\b", r"\bsyrup\b"]),

    # --- People / social ---
    _theme(
        "people",
        "People",
        "people",
        [r"\bpeople\b", r"\bperson\b", r"\bpersons\b", r"\bfolk\b", r"\btribe\b", r"\bnation\b"],
        keywords=["people", "person", "folk", "tribe", "nation"],
    ),
    _lemma("man", "Man", "people", ["man", "men", "male", "boy", "boys"], parent="people",
           extra_patterns=[r"\bhe is a man\b", r"\byoung man\b", r"\bold man\b"],
           exclude=[r"\bmany\b", r"\bhuman\b", r"\bmaneuver\b", r"\bmanage\b", r"\bmanifest\b", r"\bmanitou\b"]),
    _lemma("woman", "Woman", "people", ["woman", "women", "female", "girl", "girls", "lady"], parent="people"),
    _lemma("chief", "Chief", "people", ["chief", "chiefs", "sachem", "leader"], parent="people"),
    _lemma("friend", "Friend", "people", ["friend", "friends", "friendship", "companion", "comrade", "ally"], parent="people",
           extra_patterns=[r"\bhe is a friend\b", r"\bhas a friend\b", r"\btoken of friendship\b"]),
    _lemma("enemy", "Enemy / war", "people", ["enemy", "enemies", "war", "warfare", "warrior", "battle", "fight", "fighting"], parent="people",
           exclude=[r"\bfight\s+against\s+sleep\b"]),
    _lemma("sick", "Sick / illness", "people", ["sick", "illness", "ill", "disease", "fever", "pain", "ache", "wound", "wounded", "medicine", "heal", "healing", "cure"], parent=None),
    _lemma("dead", "Death", "people", ["dead", "death", "die", "dies", "died", "dying", "kill", "kills", "killed", "killing", "corpse", "grave"], parent=None,
           exclude=[r"\bdie\s+out\b", r"\bdying\s+out\b", r"\bfire dies\b", r"\bdies down\b"]),
    _lemma("alive", "Life / live", "people", ["alive", "life", "live", "lives", "living"], parent=None,
           exclude=[r"\blive\s+(in|at|on|with|among)\b", r"\bliving\s+(in|at|on|with)\b"]),
    _lemma("spirit", "Spirit / ghost", "people", ["spirit", "spirits", "ghost", "ghosts", "soul", "souls", "apparition"], parent=None,
           exclude=[r"\bspirit\s+of\s+(adventure|the\s+law)\b"]),
    _theme(
        "hunt",
        "Hunt / game",
        "survival",
        [r"\bhunt\b", r"\bhunting\b", r"\bhunter\b", r"\bhunted\b", r"\bgame\b", r"\bprey\b", r"\bstalk\b"],
        keywords=["hunt", "hunting", "hunter", "game", "prey", "stalk"],
        exclude=[r"\bgame\s+(of|with)\b", r"\bvideo\s+game\b", r"\blacrosse\b", r"\bdish game\b", r"\bgames of chance\b"],
        description="Hunting and game animals as quarry",
    ),

    # --- Survival & action (root-meaning / life-skill clusters) ---
    _theme(
        "hide",
        "Hide / conceal",
        "survival",
        [
            r"\bhide[s]?\b", r"\bhiding\b", r"\bhidden\b",
            r"\bconceal\b", r"\bconceals\b", r"\bconcealed\b", r"\bconcealment\b",
            r"\bfurtive\b", r"\bsneak\b", r"\bsneaks\b", r"\bsneaking\b",
            r"\bsecret\b", r"\bdisappear\b", r"\bdisappears\b",
            r"\bhides himself\b", r"\bhides away\b", r"\bwithdraws behind\b",
        ],
        keywords=["hide", "hides", "hiding", "hidden", "conceal", "furtive", "sneak", "secret", "disappear"],
        exclude=[
            r"\bhide\s+(stretcher|tanning|for tanning|scraper)\b",
            r"\bhides?\s+(for tanning|and leather|or leather|fabric)\b",
            r"\bhandles fabric, hides\b",
            r"\bprepares hides\b",
            r"\bwash(es)? (clothes, )?hides\b",
            r"\bhide scraper\b",
            r"\bfabric,?\s*hide\b",
            r"\bdirty fabric, hide\b",
            r"\bstretch hides\b",
            r"\btanning\b",
        ],
        headword_patterns=[
            r"\|kα-\|",  # hide root as headword
            r"^kὰləso", r"^kαtso", r"^kὰtso", r"kʷάsohke", r"kʷαsohke",
        ],
        description="Hiding, concealing, furtive action (not animal hide/skin as material)",
        confidence="high",
    ),
    _theme(
        "find",
        "Find / search",
        "survival",
        [
            r"\bfind\b", r"\bfinds\b", r"\bfinding\b", r"\bfound\b",
            r"\bsearch\b", r"\bsearches\b", r"\bsearching\b",
            r"\bseek\b", r"\bseeks\b", r"\bseeking\b", r"\bsought\b",
            r"\bdiscover\b", r"\bdiscovers\b", r"\bdiscovered\b",
            r"\blocate\b", r"\blocates\b", r"\blocated\b",
            r"\blook for\b", r"\blooking for\b", r"\blooks for\b",
        ],
        keywords=["find", "finds", "found", "search", "searches", "seek", "discover", "locate"],
        exclude=[r"\bfound\s+(ation|er|ry)\b", r"\bprofound\b"],
        description="Finding, searching, seeking, locating",
    ),
    _theme(
        "track",
        "Track / trail",
        "survival",
        [
            r"\btrack\b", r"\btracks\b", r"\btracking\b", r"\btracked\b",
            r"\btrail\b", r"\btrails\b", r"\bfootprint\b", r"\bfootprints\b",
            r"\bspoor\b", r"\bscent\b(?!\s+gland)", r"\bfollow\b", r"\bfollows\b", r"\bfollowing\b",
        ],
        keywords=["track", "tracks", "tracking", "trail", "trails", "footprint", "follow", "scent"],
        exclude=[r"\bfollow\s+(suit|through|up)\b", r"\btrail\s+off\b"],
        description="Tracking, trails, following sign",
    ),
    _theme(
        "location",
        "Place / direction",
        "survival",
        [
            r"\bplace\b", r"\bplaces\b", r"\blocation\b", r"\blocale\b",
            r"\bdirection\b", r"\btoward\b", r"\btowards\b", r"\byonder\b",
            r"\bbeyond\b", r"\bbehind\b", r"\bbeside\b", r"\bnearby\b",
            r"\bpath\b", r"\bpaths\b", r"\broad\b", r"\broads\b",
            r"\bwhere\b", r"\bwhence\b", r"\bthither\b",
            r"\bin that direction\b", r"\bin this direction\b",
            r"\bportage\b", r"\bcamping place\b", r"\bdwelling place\b",
        ],
        keywords=["place", "location", "locale", "direction", "toward", "path", "trail", "yonder", "beyond", "portage"],
        exclude=[r"\bplace\s+(the|his|her|my|a\s+hand|in\s+order)\b", r"\btakes place\b"],
        description="Places, paths, and directional location (not every use of 'there')",
    ),
    _theme(
        "hurt",
        "Hurt / injury",
        "survival",
        [
            r"\bhurt\b", r"\bhurts\b", r"\bhurting\b",
            r"\binjure\b", r"\binjures\b", r"\binjured\b", r"\binjury\b",
            r"\bwound\b", r"\bwounds\b", r"\bwounded\b",
            r"\bpain\b", r"\bpainful\b", r"\bache\b", r"\baches\b", r"\baking\b",
            r"\bbruise\b", r"\bbruises\b", r"\bbruised\b",
            r"\bbleed\b", r"\bbleeds\b", r"\bbleeding\b", r"\bbloody\b",
            r"\bburn\b", r"\bburns\b", r"\bburned\b", r"\bburning\b(?!\s+with\s+desire)",
            r"\bcut\b", r"\bcuts\b", r"\bcutting\b",
            r"\bbreak[s]?\s+(his|her|a|the|one's|own)\b", r"\bbroken\s+(leg|arm|bone|head|back|neck)\b",
            r"\bstrike[s]?\b", r"\bstruck\b", r"\bhit[s]?\b(?!\s+upon)",
        ],
        keywords=["hurt", "injury", "wound", "wounded", "pain", "ache", "bruise", "bleed", "burn", "cut"],
        exclude=[
            r"\bcut\s+(off|down|through|across|short)\b",
            r"\bbreak[s]?\s+(camp|down|into|up|away|off|open|news)\b",
            r"\bstrike\s+(out|up|a\s+bargain|camp)\b",
        ],
        description="Injury, pain, wounds, blows",
    ),
    _theme(
        "defend",
        "Defend / protect",
        "survival",
        [
            r"\bdefend\b", r"\bdefends\b", r"\bdefending\b", r"\bdefense\b", r"\bdefence\b",
            r"\bprotect\b", r"\bprotects\b", r"\bprotecting\b", r"\bprotection\b",
            r"\bguard\b", r"\bguards\b", r"\bguarding\b",
            r"\bshield\b", r"\bward\s+off\b", r"\bfight back\b", r"\bdefend himself\b",
            r"\bresist\b", r"\bresists\b", r"\bresisting\b",
        ],
        keywords=["defend", "defense", "protect", "protection", "guard", "shield", "resist"],
        description="Defending, protecting, resisting attack",
        confidence="high",
    ),
    _theme(
        "pretend",
        "Pretend / mimic",
        "survival",
        [
            r"\bpretend\b", r"\bpretends\b", r"\bpretending\b",
            r"\bimitate\b", r"\bimitates\b", r"\bimitating\b", r"\bimitation\b",
            r"\bmimic\b", r"\bmimics\b", r"\bmimicking\b",
            r"\bfeign\b", r"\bfeigns\b", r"\bfeigning\b",
            r"\bmake believe\b", r"\bmakes believe\b",
            r"\bacts? like\b", r"\bbehaves? like\b",
            r"\bemulates\b", r"\bemulate\b",
            r"\bcalls? like\b", r"\bsounds? like a\b", r"\bsmells? like a\b",
            r"\bplays raccoon\b", r"\bape[sd]?\b",
        ],
        keywords=[
            "pretend", "pretends", "imitate", "mimic", "feign", "feigns",
            "disguise", "emulate", "make believe",
        ],
        headword_patterns=[
            r"kkαləso$",  # pretends-to-be construction
            r"\|amahs-\|",  # imitate root
        ],
        description="Pretending, imitating, acting/calling/smelling like — mimicry cluster",
        confidence="high",
    ),
    _theme(
        "fear",
        "Fear / danger",
        "survival",
        [
            r"\bfear\b", r"\bfears\b", r"\bafraid\b",
            r"\bfrighten\b", r"\bfrightens\b", r"\bfrightened\b", r"\bfright\b",
            r"\bscare\b", r"\bscares\b", r"\bscared\b",
            r"\bstartle\b", r"\bstartles\b", r"\bstartled\b",
            r"\bdanger\b", r"\bdangerous\b", r"\bthreat\b", r"\bthreaten\b",
            r"\balarm\b", r"\bterror\b", r"\bdread\b",
        ],
        keywords=["fear", "afraid", "frighten", "frightened", "scare", "startle", "danger", "threat", "alarm"],
        description="Fear, startle, danger, threat",
    ),
    _theme(
        "flee",
        "Flee / escape",
        "survival",
        [
            r"\bflee\b", r"\bflees\b", r"\bfled\b", r"\bfleeing\b", r"\bflight\b",
            r"\bescape\b", r"\bescapes\b", r"\bescaped\b", r"\bescaping\b",
            r"\brun away\b", r"\bruns away\b", r"\bflee from\b",
            r"\bsurvive\b", r"\bsurvives\b", r"\bsurviving\b", r"\bsurvival\b",
            r"\brescue\b", r"\brescues\b", r"\brescued\b",
            r"\bsave\b", r"\bsaves\b", r"\bsaved\b(?!\s+money)",
        ],
        keywords=["flee", "flees", "escape", "escapes", "flight", "survive", "rescue", "save", "run away"],
        exclude=[r"\bflight\s+of\s+(stairs|fancy)\b", r"\bsave\s+(money|time|face)\b"],
        description="Fleeing, escaping, surviving, rescue",
    ),
    _theme(
        "attack",
        "Attack / strike",
        "survival",
        [
            r"\battack\b", r"\battacks\b", r"\battacking\b",
            r"\bstrike\b", r"\bstrikes\b", r"\bstruck\b",
            r"\bwar\b", r"\bwarfare\b", r"\bwarrior\b",
            r"\benemy\b", r"\benemies\b",
            r"\bcaptive\b", r"\bcaptives\b", r"\bprisoner\b", r"\bprisoners\b",
            r"\bsteal\b", r"\bsteals\b", r"\bstolen\b", r"\brob\b", r"\brobs\b",
            r"\bforce\b", r"\bforces\b", r"\bforced\b",
        ],
        keywords=["attack", "strike", "war", "warfare", "enemy", "captive", "prisoner", "steal", "force"],
        exclude=[
            r"\bstrike\s+(out|up|a\s+bargain|camp|oil)\b",
            r"\bforce\s+(of\s+habit|open)\b",
            r"\bwar\s+(whoop|dance|paint)\b",  # keep paint/dance — actually keep those, they're war-related
        ],
        description="Attack, war, capture, force, theft",
    ),
    _theme(
        "cover_shelter",
        "Cover / shelter",
        "survival",
        [
            r"\bcover\b", r"\bcovers\b", r"\bcovering\b", r"\bcovered\b",
            r"\bshelter\b", r"\bshelters\b", r"\bsheltered\b",
            r"\bblanket\b", r"\bblankets\b",
            r"\bshade\b", r"\bshadow\b",
            r"\bwrap\b", r"\bwraps\b", r"\bwrapped\b",
        ],
        keywords=["cover", "covers", "covering", "shelter", "shade", "shadow", "wrap"],
        exclude=[r"\bcover\s+(charge|story|letter)\b", r"\bunder cover of\b"],
        description="Covering, sheltering, wrapping for protection or concealment",
    ),
    _theme(
        "trap_catch",
        "Trap / catch",
        "survival",
        [
            r"\btrap\b", r"\btraps\b", r"\btrapping\b", r"\btrapped\b",
            r"\bsnare\b", r"\bsnares\b", r"\bsnared\b",
            r"\bbait\b", r"\blure\b", r"\blures\b",
            r"\bcatch\b", r"\bcatches\b", r"\bcatching\b", r"\bcaught\b",
            r"\bquarry\b", r"\bweir\b",
        ],
        keywords=["trap", "traps", "snare", "bait", "lure", "catch", "catches", "caught", "quarry", "weir"],
        exclude=[r"\bcatch\s+(cold|fire|up|on)\b", r"\btrap\s+door\b"],
        description="Trapping, snaring, catching game or fish",
    ),
    _theme(
        "gather",
        "Gather / fetch",
        "survival",
        [
            r"\bgather\b", r"\bgathers\b", r"\bgathering\b",
            r"\bfetch\b", r"\bfetches\b", r"\bfetching\b",
            r"\bcollect\b", r"\bcollects\b", r"\bcollecting\b",
            r"\bpick\b", r"\bpicks\b", r"\bpicking\b",
            r"\bharvest\b", r"\bharvests\b", r"\bharvesting\b",
        ],
        keywords=["gather", "gathering", "fetch", "collect", "pick", "picking", "harvest"],
        exclude=[r"\bpick\s+(a\s+fight|up\s+speed|on)\b", r"\bpicks?\s+his\s+own\b"],
        description="Gathering, fetching, harvesting resources",
    ),

    # --- Motion ---
    _lemma("walk", "Walk", "motion", ["walk", "walks", "walking", "walked", "stroll"], parent=None),
    _lemma("run", "Run", "motion", ["run", "runs", "running", "ran", "sprint"], parent=None,
           exclude=[r"\brun\s+(out\s+of|into\s+debt|the\s+risk)\b"]),
    _lemma("swim", "Swim", "motion", ["swim", "swims", "swimming", "swam"], parent=None),
    _lemma("sit", "Sit", "motion", ["sit", "sits", "sitting", "sat", "seat"], parent=None),
    _lemma("stand", "Stand", "motion", ["stand", "stands", "standing", "stood"], parent=None,
           exclude=[r"\bstand\s+for\b", r"\boutstanding\b", r"\bunderstand\b"]),
    _lemma("carry", "Carry", "motion", ["carry", "carries", "carrying", "carried", "portage", "haul"], parent=None),
    _lemma("come", "Come / arrive", "motion", ["come", "comes", "coming", "came", "arrive", "arrives", "arrived", "arrival"], parent=None),
    _lemma("go_leave", "Go / leave", "motion", ["leave", "leaves", "leaving", "left", "depart", "departed", "go away", "goes away"], parent=None,
           extra_patterns=[r"\bgo\s+away\b", r"\bgoes\s+away\b", r"\bgoing\s+away\b", r"\bhe\s+goes\b", r"\bhe\s+went\b"]),

    # --- Perception / speech ---
    _lemma("see", "See / look", "perception", ["see", "sees", "seeing", "saw", "seen", "look", "looks", "looking", "watch", "gaze"], parent=None,
           exclude=[r"\blook\s+(like|as\s+if|after|for\s+trouble)\b", r"\bseesaw\b"]),
    _lemma("hear", "Hear / listen", "perception", ["hear", "hears", "hearing", "heard", "listen", "listens", "listening"], parent=None),
    _lemma("know", "Know / think", "perception", ["know", "knows", "knowing", "knew", "known", "think", "thinks", "thinking", "thought", "remember", "forget"], parent=None),
    _lemma("speak", "Speak / say", "perception", ["speak", "speaks", "speaking", "spoke", "spoken", "say", "says", "saying", "said", "tell", "tells", "told", "talk", "speech", "voice"], parent=None),
    _lemma("sing", "Sing", "perception", ["sing", "sings", "singing", "sang", "sung", "song", "songs"], parent=None),
    _lemma("dance", "Dance", "perception", ["dance", "dances", "dancing", "danced"], parent=None),
    _lemma("sleep", "Sleep", "perception", ["sleep", "sleeps", "sleeping", "slept", "asleep", "dream", "dreams", "dreaming", "wake", "wakes", "waking", "awake"], parent=None),
    _lemma("cry", "Cry / weep", "perception", ["cry", "cries", "crying", "cried", "weep", "weeping", "tears"], parent=None,
           exclude=[r"\bcry\s+out\s+for\b", r"\bwar\s+cry\b"]),
    _lemma("laugh", "Laugh", "perception", ["laugh", "laughs", "laughing", "laughed", "smile"], parent=None),
    _lemma("fall", "Fall / drop", "motion", ["fall", "falls", "falling", "fell", "fallen", "drop", "drops", "dropping", "tumble"], parent=None,
           exclude=[r"\bfall\s+(in\s+love|short|apart)\b", r"\bfalls\s+(short|in\s+love)\b", r"\bwaterfall\b"]),
    _theme(
        "color",
        "Color",
        "perception",
        [
            r"\bcolor\b", r"\bcolour\b", r"\bcolored\b", r"\bcoloured\b",
            r"\bred\b", r"\bwhite\b", r"\bblack\b", r"\bblue\b", r"\byellow\b", r"\bgreen\b",
            r"\bbrown\b", r"\bgray\b", r"\bgrey\b", r"\bpink\b", r"\borange\b",
        ],
        keywords=["color", "red", "white", "black", "blue", "yellow", "green", "brown", "gray"],
        exclude=[r"\bred\s+(hot|handed)\b", r"\bblack\s+(out|and\s+blue)\b"],
        description="Color terms in glosses",
        confidence="medium",
    ),
]


# Precompile patterns once (full scan is ~10k entries × many tags).
_COMPILED: list[dict] = []


def _ensure_compiled() -> list[dict]:
    global _COMPILED
    if _COMPILED:
        return _COMPILED
    for tag in TAGS:
        _COMPILED.append({
            **tag,
            "_include": [re.compile(p, re.I) for p in (tag.get("english_patterns") or [])],
            "_exclude": [re.compile(p, re.I) for p in (tag.get("exclude_patterns") or [])],
            "_headword": [re.compile(p, re.I) for p in (tag.get("headword_patterns") or [])],
        })
    return _COMPILED


def tag_matches(english: str, tag: dict, headword: str = "") -> tuple[bool, str, str]:
    """Return (matched, reason, confidence). Matches English gloss and optional headword patterns."""
    en = english or ""
    en_low = en.lower()
    hw = headword or ""
    for rx in tag.get("_exclude") or []:
        if rx.search(en_low):
            # v1: any exclude kills the tag (precision over recall).
            return False, "", ""
    reason = ""
    raw_pats = tag.get("english_patterns") or []
    for i, rx in enumerate(tag.get("_include") or []):
        if rx.search(en):
            reason = f"English: {raw_pats[i] if i < len(raw_pats) else rx.pattern}"
            break
    if not reason and hw:
        raw_hw = tag.get("headword_patterns") or []
        for i, rx in enumerate(tag.get("_headword") or []):
            if rx.search(hw):
                reason = f"Headword: {raw_hw[i] if i < len(raw_hw) else rx.pattern}"
                break
    if not reason:
        return False, "", ""
    conf = tag.get("confidence") or "medium"
    if tag.get("group") in ("animals", "plants") and tag.get("specificity") == "lemma":
        if "⟨sciname⟩" in en or "sciname" in en_low:
            conf = "high"
    if tag.get("specificity") == "meta":
        conf = "high"
    # Morph cue alone is still useful but slightly softer unless English also hit
    if reason.startswith("Headword:") and conf == "high":
        conf = "medium"
    return True, reason, conf


def audio_paths(entry: dict) -> tuple[str, str]:
    main = alt = ""
    for a in entry.get("audio", []):
        lp = a.get("local_path", "")
        if a.get("type") == "guide":
            alt = lp
        else:
            main = lp
    return main, alt


def build_index(entries: dict) -> dict:
    by_entry: dict[str, list[dict]] = defaultdict(list)
    by_tag: dict[str, list[dict]] = defaultdict(list)
    tag_by_id = {t["id"]: t for t in TAGS}

    compiled = _ensure_compiled()

    for entry in entries.values():
        eid = entry["id"]
        en = entry.get("english") or ""
        if len(en.strip()) < 2:
            continue
        main, alt = audio_paths(entry)
        card_base = {
            "entry_id": eid,
            "headword": entry.get("headword", ""),
            "english": en,
            "part_of_speech": entry.get("part_of_speech", ""),
            "audio_main": main,
            "audio_alt": alt,
        }

        hw = entry.get("headword", "")
        for tag in compiled:
            ok, reason, conf = tag_matches(en, tag, headword=hw)
            if not ok:
                continue
            hit = {
                "tag_id": tag["id"],
                "group": tag["group"],
                "label": tag["label"],
                "specificity": tag["specificity"],
                "parent": tag.get("parent"),
                "confidence": conf,
                "reason": reason,
            }
            by_entry[eid].append(hit)

            card = {
                **card_base,
                "confidence": conf,
                "match_reasons": [reason],
            }
            by_tag[tag["id"]].append(card)

    for tid in by_tag:
        by_tag[tid].sort(key=lambda x: (x.get("headword") or "").lower())

    # Public catalog without compiled regex noise for consumers that only need labels
    catalog_tags = []
    for t in TAGS:
        catalog_tags.append({
            "id": t["id"],
            "label": t["label"],
            "group": t["group"],
            "specificity": t["specificity"],
            "parent": t.get("parent"),
            "description": t.get("description", ""),
            "keywords": t.get("keywords") or [],
            "confidence_default": t.get("confidence", "medium"),
        })

    tagged_entries = len(by_entry)
    tag_hits = sum(len(v) for v in by_entry.values())

    return {
        "meta": {
            "source": "entries.json",
            "tag_count": len(TAGS),
            "group_count": len(GROUPS),
            "tagged_entries": tagged_entries,
            "tag_hits": tag_hits,
        },
        "groups": GROUPS,
        "tags": catalog_tags,
        "by_entry": dict(by_entry),
        "by_tag": dict(by_tag),
    }


def attach_tags_to_english_index(tag_index: dict) -> None:
    """Enrich english_index.json entries with tags[] for Lab scoring."""
    if not ENGLISH_INDEX_JSON.exists():
        return
    data = load_json(ENGLISH_INDEX_JSON, {"entries": [], "total": 0})
    by_entry = tag_index.get("by_entry") or {}
    for item in data.get("entries") or []:
        eid = item.get("entry_id")
        hits = by_entry.get(eid) or []
        item["tags"] = [h["tag_id"] for h in hits]
        item["tag_meta"] = [
            {
                "id": h["tag_id"],
                "group": h["group"],
                "specificity": h["specificity"],
                "confidence": h["confidence"],
            }
            for h in hits
        ]
    save_json(ENGLISH_INDEX_JSON, data)


def print_report(index: dict, samples: int = 3) -> None:
    meta = index["meta"]
    print(
        f"Semantic tags: {meta['tag_count']} tags, "
        f"{meta['tagged_entries']} tagged entries, {meta['tag_hits']} hits"
    )
    by_tag = index.get("by_tag") or {}
    tag_by_id = {t["id"]: t for t in index.get("tags") or []}
    rows = []
    for t in index.get("tags") or []:
        n = len(by_tag.get(t["id"], []))
        rows.append((n, t["group"], t["label"], t["id"]))
    rows.sort(reverse=True)
    for n, group, label, tid in rows:
        if n == 0:
            continue
        print(f"  [{group}] {label} ({tid}): {n}")
        for card in (by_tag.get(tid) or [])[:samples]:
            en = (card.get("english") or "")[:90].replace("\n", " ")
            print(f"      · {card.get('headword')}: {en}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine semantic tags from English glosses")
    parser.add_argument("--report", action="store_true", help="Print per-tag samples")
    parser.add_argument("--samples", type=int, default=2, help="Samples per tag in report")
    parser.add_argument("--no-english-index", action="store_true", help="Skip enriching english_index.json")
    args = parser.parse_args()

    ensure_dirs()
    catalog = load_json(ENTRIES_JSON, {"entries": {}})
    entries = catalog.get("entries", {})
    if not entries:
        print("No entries. Run spider.py first.")
        return 1

    index = build_index(entries)
    save_json(SEMANTIC_TAGS_JSON, index)
    print(
        f"Wrote {SEMANTIC_TAGS_JSON} — "
        f"{index['meta']['tagged_entries']} entries, {index['meta']['tag_hits']} tag hits"
    )

    if not args.no_english_index:
        attach_tags_to_english_index(index)
        if ENGLISH_INDEX_JSON.exists():
            print(f"Enriched {ENGLISH_INDEX_JSON} with tags[]")

    if args.report:
        print_report(index, samples=args.samples)
    else:
        # Compact summary: top tags
        by_tag = index.get("by_tag") or {}
        top = sorted(
            ((len(v), tid) for tid, v in by_tag.items()),
            reverse=True,
        )[:15]
        print("Top tags:", ", ".join(f"{tid}={n}" for n, tid in top))

    empty = [t["id"] for t in TAGS if not (index.get("by_tag") or {}).get(t["id"])]
    if empty:
        print(f"Empty tags ({len(empty)}): {', '.join(empty[:20])}{'…' if len(empty) > 20 else ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
