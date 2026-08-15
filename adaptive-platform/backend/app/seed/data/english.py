"""English vocabulary seed content.

Each entry: (word, meaning, context sentence with ___, frequency band, difficulty).

`band` is the vocabulary band the word sits in (spec §21) and drives which
words are introduced first. `difficulty` is the author's estimate (spec §35);
real performance recalibrates it later via `observed_difficulty`.

Every word here has a matching photo in ../images and a Piper audio clip in
../audio, so the child app can show and speak it offline.
"""

WORDS: list[tuple[str, str, str, int, float]] = [
    # --- band 500: earliest, shortest, most regular spellings ---------------
    ("cat",    "a small furry pet that says meow",          "The ___ sat on the mat.",            500, 0.10),
    ("dog",    "a pet animal that barks",                    "The ___ wagged its tail.",           500, 0.12),
    ("car",    "a vehicle with four wheels",                 "Dad drove the ___ to school.",       500, 0.12),
    ("hat",    "something you wear on your head",            "Put on your woolly ___.",            500, 0.12),
    ("bus",    "a long vehicle that carries many people",    "We waited for the ___.",             500, 0.15),
    ("box",    "a container with straight sides",            "Put the toys in the ___.",           500, 0.15),
    ("cup",    "a small container you drink from",           "Fill the ___ with water.",           500, 0.15),
    ("ball",   "a round thing you throw or kick",            "He kicked the ___ hard.",            500, 0.18),
    ("egg",    "an oval food that comes from a hen",         "I boiled an ___ for breakfast.",     500, 0.18),
    ("book",   "pages with words that you read",             "She read a ___ at bedtime.",         500, 0.20),
    ("fish",   "an animal that lives in water",              "A silver ___ swam past.",            500, 0.20),
    ("bird",   "an animal with feathers that can fly",       "The ___ built a nest.",              500, 0.22),
    ("milk",   "a white drink that comes from cows",         "Pour the ___ into the jug.",         500, 0.25),
    ("tree",   "a tall plant with a trunk and branches",     "We sat under the ___.",              500, 0.25),
    ("house",  "a building where people live",               "We painted the ___ blue.",           500, 0.30),
    ("apple",  "a round fruit that is red or green",         "I ate a juicy ___.",                 500, 0.25),

    # --- band 1000 ---------------------------------------------------------
    ("bee",    "a small insect that makes honey",            "A ___ buzzed past my ear.",         1000, 0.12),
    ("bat",    "an animal with wings that flies at night",   "A ___ hung upside down.",           1000, 0.15),
    ("cow",    "a farm animal that gives milk",              "The ___ ate the grass.",            1000, 0.15),
    ("pig",    "a pink farm animal",                         "The ___ rolled in the mud.",        1000, 0.15),
    ("ant",    "a tiny insect that lives in a big group",    "An ___ carried a crumb.",           1000, 0.15),
    ("frog",   "a green animal that hops and swims",         "The ___ jumped into the pond.",     1000, 0.22),
    ("duck",   "a bird that swims and quacks",               "The ___ swam on the pond.",         1000, 0.22),
    ("cake",   "a sweet food you eat at parties",            "We shared a birthday ___.",         1000, 0.22),
    ("boat",   "something that carries people on water",     "We rowed the little ___.",          1000, 0.25),
    ("key",    "a metal thing that opens a lock",            "I lost the front door ___.",        1000, 0.25),
    ("bear",   "a big furry animal with strong claws",       "The ___ ate the berries.",          1000, 0.28),
    ("moon",   "the bright round shape in the night sky",    "The ___ was full and bright.",      1000, 0.28),
    ("lion",   "a big wild cat with a shaggy mane",          "The ___ roared loudly.",            1000, 0.30),
    ("clock",  "a thing that shows you the time",            "The ___ struck three.",             1000, 0.35),
    ("bread",  "food made from flour that you bake",         "I made toast from the ___.",        1000, 0.35),
    ("horse",  "a big animal you can ride",                  "She rode the ___ across the field.",1000, 0.35),
    ("sheep",  "a farm animal with woolly fur",              "The ___ ate grass on the hill.",    1000, 0.38),
    ("plane",  "a machine that flies through the sky",       "The ___ took off into the clouds.", 1000, 0.40),
    ("train",  "carriages that run along rails",             "The ___ left the station.",         1000, 0.40),
    ("flower", "the colourful part of a plant",              "She picked a yellow ___.",          1000, 0.40),
    ("mouse",  "a small animal with a long thin tail",       "A ___ ran under the door.",         1000, 0.42),

    # --- band 1500 ---------------------------------------------------------
    ("fox",    "a wild animal with a bushy tail",            "The ___ ran into the woods.",       1500, 0.15),
    ("goat",   "a farm animal that likes to climb",          "The ___ climbed onto the rock.",    1500, 0.25),
    ("owl",    "a bird that hunts at night",                 "The ___ hooted in the dark.",       1500, 0.30),
    ("gift",   "something you give to someone",              "I wrapped the ___ in paper.",       1500, 0.30),
    ("drum",   "something you hit to make a beat",           "He banged the ___ loudly.",         1500, 0.32),
    ("kite",   "a toy that flies at the end of a string",    "The ___ flew high above us.",       1500, 0.35),
    ("candy",  "a small sweet treat",                        "He ate one last ___.",              1500, 0.40),
    ("lemon",  "a sour yellow fruit",                        "The ___ made me pull a face.",      1500, 0.40),
    ("pizza",  "flat bread with cheese melted on top",       "We shared a big ___.",              1500, 0.40),
    ("snake",  "a long animal that has no legs",             "The ___ slid through the grass.",   1500, 0.40),
    ("tiger",  "a big wild cat with orange stripes",         "The ___ prowled through the trees.",1500, 0.40),
    ("grape",  "a small round fruit that grows in bunches",  "He ate one purple ___.",            1500, 0.42),
    ("honey",  "a sweet sticky food made by bees",           "I spread ___ on my toast.",         1500, 0.42),
    ("banana", "a long yellow fruit you peel",               "The monkey peeled a ___.",          1500, 0.45),
    ("carrot", "a long orange vegetable",                    "The rabbit ate a crunchy ___.",     1500, 0.45),
    ("pencil", "a thin thing you write and draw with",       "Sharpen your ___ please.",          1500, 0.45),
    ("monkey", "an animal that climbs and swings in trees",  "The ___ swung down from a branch.", 1500, 0.50),
    ("rabbit", "a small animal with long ears that hops",    "The ___ hopped away quickly.",      1500, 0.50),
    ("balloon","a bag of air on a string",                   "The red ___ floated away.",         1500, 0.55),
    ("elephant","a huge grey animal with a long trunk",      "The ___ sprayed water everywhere.", 1500, 0.66),

    # --- band 2000 ---------------------------------------------------------
    ("panda",  "a black and white bear that eats bamboo",    "The ___ chewed a bamboo shoot.",    2000, 0.40),
    ("shark",  "a big fish with very sharp teeth",           "A ___ swam past the boat.",         2000, 0.40),
    ("mango",  "a sweet orange fruit from a hot country",    "She sliced the ripe ___.",          2000, 0.42),
    ("melon",  "a big juicy fruit with lots of seeds",       "We shared a cold ___.",             2000, 0.42),
    ("camel",  "a desert animal with a hump on its back",    "The ___ walked across the sand.",   2000, 0.45),
    ("onion",  "a vegetable made of layers that stings",     "Chop the ___ finely.",              2000, 0.45),
    ("peach",  "a soft sweet fruit with fuzzy skin",         "The ___ was perfectly ripe.",       2000, 0.45),
    ("whale",  "the biggest animal in the sea",              "The ___ dived deep down.",          2000, 0.45),
    ("zebra",  "a horse with black and white stripes",       "The ___ galloped across the plain.",2000, 0.45),
    ("donut",  "a round sweet cake with a hole in it",       "He picked a sugary ___.",           2000, 0.45),
    ("hammer", "a tool for hitting nails",                   "He used a ___ to fix the shed.",    2000, 0.48),
    ("ladder", "steps you climb to reach high places",       "He climbed the wooden ___.",        2000, 0.48),
    ("koala",  "a grey animal that eats leaves and sleeps",  "The ___ slept high in the tree.",   2000, 0.50),
    ("turtle", "an animal with a hard shell on its back",    "The ___ crawled slowly to the sea.",2000, 0.50),
    ("camera", "a thing you use to take photographs",        "She took a photo with her ___.",    2000, 0.50),
    ("cherry", "a small round red fruit with a stone",       "One ___ sat on top of the cake.",   2000, 0.50),
    ("rocket", "a machine that flies up into space",         "The ___ blasted off.",              2000, 0.55),
    ("castle", "a huge stone building where a king lived",   "The ___ had four tall towers.",     2000, 0.55),
    ("guitar", "an instrument with strings you strum",       "She played the ___ softly.",        2000, 0.58),
    ("penguin","a black and white bird that swims",          "The ___ waddled over the ice.",     2000, 0.60),
    ("dolphin","a clever sea animal that leaps and clicks",  "A ___ jumped out of the waves.",    2000, 0.60),
    ("rainbow","a coloured arch in the sky after rain",      "A ___ appeared over the hills.",    2000, 0.60),
    ("umbrella","something you hold to keep the rain off",   "She opened her spotty ___.",        2000, 0.66),
    ("dinosaur","a huge animal that lived long, long ago",   "The ___ left enormous footprints.", 2000, 0.68),
    ("butterfly","an insect with big patterned wings",       "A ___ landed on the flower.",       2000, 0.65),

    # --- band 3000: longest words, trickiest spellings ---------------------
    ("octopus","a sea animal with eight long arms",          "The ___ hid among the rocks.",      3000, 0.65),
    ("kangaroo","an animal that hops and carries its baby",  "The ___ bounded across the field.", 3000, 0.68),
    ("sunflower","a very tall flower that follows the sun",  "The ___ grew taller than me.",      3000, 0.68),
    ("chocolate","a sweet brown treat that melts",           "She melted the ___ in a pan.",      3000, 0.70),
    ("hamburger","a sandwich with a round bun",              "He ordered a ___ and chips.",       3000, 0.70),
    ("telephone","a thing you use to talk to someone far away","The old ___ rang loudly.",        3000, 0.70),
    ("crocodile","a big reptile with strong snapping jaws",  "A ___ slid into the river.",        3000, 0.72),
    ("pineapple","a spiky fruit that is sweet inside",       "We cut the ___ into chunks.",       3000, 0.72),
    ("watermelon","a big green fruit that is red inside",    "We ate cold ___ in the garden.",    3000, 0.74),
    ("strawberry","a small red fruit with seeds on the outside","She picked a ripe ___.",         3000, 0.75),
    ("helicopter","a flying machine with spinning blades",   "The ___ landed on the field.",      3000, 0.78),
]

# Concepts that are easier to spell once a shorter relative is known. These
# become explicit prerequisite edges (spec §28) so the engine never introduces
# the long word before the short one is understood.
PREREQUISITES: dict[str, list[str]] = {
    "butterfly": ["bee"],
    "strawberry": ["cherry"],
    "watermelon": ["melon"],
    "pineapple": ["apple"],
    "sunflower": ["flower"],
    "helicopter": ["plane"],
    "hamburger": ["bread"],
}


SKILL_TREE = {
    "slug": "english",
    "name": "English",
    "icon": "book-open",
    "skills": [
        {
            "slug": "vocabulary",
            "name": "Vocabulary",
            "child_name": "Knowing words",
            "children": [
                {"slug": "recognition", "name": "Recognition", "child_name": "Spotting words"},
                {"slug": "meaning", "name": "Meaning", "child_name": "What words mean"},
                {"slug": "context", "name": "Context", "child_name": "Using words"},
            ],
        },
        {
            "slug": "spelling",
            "name": "Spelling",
            "child_name": "Spelling",
            "children": [
                {"slug": "simple-words", "name": "Simple Words", "child_name": "Short words"},
                {"slug": "word-patterns", "name": "Word Patterns", "child_name": "Longer words"},
            ],
        },
    ],
}

MILESTONES = [
    ("first-specimen", "First specimen", "concepts_mastered", 1, "leaf"),
    ("word-starter", "Word Starter", "concepts_mastered", 10, "seedling"),
    ("word-explorer", "Word Explorer", "concepts_mastered", 25, "compass"),
    ("word-adventurer", "Word Adventurer", "concepts_mastered", 50, "map-trifold"),
    ("word-wizard", "Word Wizard", "concepts_mastered", 90, "sparkle"),
    ("vocab-500", "500 words", "vocabulary_estimate", 500, "book-open"),
    ("vocab-1000", "1,000 words", "vocabulary_estimate", 1000, "books"),
    ("vocab-1500", "1,500 words", "vocabulary_estimate", 1500, "graduation-cap"),
]
