#!/usr/bin/env python3
"""Single source of truth for the original rock song "RISE FROM THE ASHES".

Everything (audio arrangement, vocal melody plan, music-video scene schedule,
lyrics) is derived from the data in this file so the song and the video stay
perfectly in sync.

Song:  "Rise From The Ashes"  -  original English female rock song
Key:   E minor, 132 BPM  ->  beat = 60/132 s, bar = 4 beats
Length: 330 s (5:30)
"""

TITLE = "Rise From The Ashes"
ARTIST = "AURORA VEIL"          # fictional original artist
BPM = 132.0
BEAT = 60.0 / BPM               # 0.4545 s
BAR = 4 * BEAT                  # 1.8182 s
SR = 44100
DURATION = 330.0                # 5:30

# ---------------------------------------------------------------- structure
# (name, start_s, end_s, energy 0..1, vocal?)
SECTIONS = [
    ("intro",    0.0,  20.0, 0.30, False),
    ("verse1",  20.0,  50.0, 0.55, True),
    ("pre1",    50.0,  65.0, 0.75, True),
    ("chorus1", 65.0, 100.0, 1.00, True),
    ("verse2", 100.0, 130.0, 0.55, True),
    ("chorus2", 130.0, 165.0, 1.00, True),
    ("solo",   165.0, 200.0, 0.90, False),
    ("bridge", 200.0, 230.0, 0.70, True),
    ("chorus3",230.0, 275.0, 1.00, True),
    ("outro",  275.0, 330.0, 0.45, True),   # vocal only 275-290, then instrumental
]

# ------------------------------------------------------------------- lyrics
LYRICS = {
"verse1": (
 "The streetlights flicker on an empty road. "
 "I'm carrying all the weight of every word you never said. "
 "The mirror shows a stranger I don't know, "
 "but I still remember how the morning used to glow. "
 "They told me I'd break, they told me I'd fall. "
 "I swallowed every punch, I took it all. "
 "Now I'm standing in the wreckage, asking who I am, "
 "and the answer is burning brighter than their plans."
),
"pre1": (
 "So light the match, watch me ignite. "
 "Every scar I carry is a reason I'm alive. "
 "I don't need your permission to shine."
),
"chorus": (
 "I rise from the ashes, I rise like a flame. "
 "Higher than the silence, louder than the shame. "
 "They buried me alive but I dug my way out. "
 "I'm the storm they feared, I'm what hope is about. "
 "Oh-oh, watch me burn. Oh-oh, watch me rise. "
 "Every bridge I've crossed, every bridge I burned, "
 "is the fire in my eyes. "
 "I rise from the ashes, I rise from the ashes tonight."
),
"verse2": (
 "Midnight rain on the window of this broken town. "
 "I used to pray for the thunder just to drown the sound "
 "of the voices in my head that said I'd never be enough. "
 "But I learned the deepest waters are what make you tough. "
 "You took my hand and you called it love, "
 "left me standing in the dark with nothing. "
 "Now I'm dancing on the grave of every lie, "
 "with my heart wide open and my head held high."
),
"bridge": (
 "And if I fall again, I'll fall into the light, "
 "'cause I've been down in the dark and I've seen the night. "
 "Every tear I cried became a river, every crack became a door. "
 "I am more than what they said I'd be, I'm so much more. "
 "So scream it to the sky, let the whole world hear: "
 "the girl they tried to break is standing right here."
),
"chorus3": (
 "I rise from the ashes, I rise like a flame. "
 "Higher than the silence, louder than the shame. "
 "They buried me alive but I dug my way out. "
 "I'm the storm they feared, I'm what hope is about. "
 "Oh-oh, watch me burn. Oh-oh, watch me rise. "
 "Every bridge I've crossed, every bridge I burned, "
 "is the fire in my eyes. "
 "I rise, I rise, I rise from the ashes tonight. "
 "No more running, no more hiding from the fight. "
 "I am the fire, I am the light. "
 "I rise from the ashes, I rise from the ashes tonight."
),
"outro": (
 "And the dawn is mine... rise... rise..."
),
}

# vocal sections that reuse the same chorus text/audio
VOCAL_SECTIONS = [
    # (section name, lyric key, start_s, end_s)
    ("verse1",  "verse1",  20.0,  50.0),
    ("pre1",    "pre1",    50.0,  65.0),
    ("chorus1", "chorus",  65.0, 100.0),
    ("verse2",  "verse2", 100.0, 130.0),
    ("chorus2", "chorus", 130.0, 165.0),   # same lyrics/audio as chorus1
    ("bridge",  "bridge", 200.0, 230.0),
    ("chorus3", "chorus3",230.0, 275.0),
    ("outro",   "outro",  275.0, 290.0),
]

# ------------------------------------------------------------------- chords
# name -> (bass midi, [guitar power-chord midis])
CHORDS = {
    "Em": (40, [52, 59, 64]),
    "C":  (36, [48, 55, 60]),
    "G":  (43, [55, 59, 62]),
    "D":  (38, [50, 57, 62]),
    "Am": (45, [57, 60, 64]),
    "F":  (41, [53, 60, 65]),
}

# chord per bar, per section pattern (cycled)
PROG = {
    "intro":   ["Em","Em","C","G","D","Em","C","G","D","D","Em"],
    "verse":   ["Em","C","G","D","Em","C","D","D"],
    "pre":     ["Em","C","G","D","Em","C","D","D"],
    "chorus":  ["Em","G","C","D","Em","G","C","D"],
    "solo":    ["Em","C","G","D"],
    "bridge":  ["Am","F","C","G","Am","F","G","G"],
    "outro":   ["Em","C","G","D"],
}

def section_of(t):
    for name, s, e, en, voc in SECTIONS:
        if s <= t < e:
            return name, s, e, en, voc
    return SECTIONS[-1][0], SECTIONS[-1][1], SECTIONS[-1][2], SECTIONS[-1][3], SECTIONS[-1][4]

def chord_at(t):
    name, s, e, en, voc = section_of(t)
    key = {"intro":"intro","verse1":"verse","verse2":"verse","pre1":"pre",
           "chorus1":"chorus","chorus2":"chorus","chorus3":"chorus",
           "solo":"solo","bridge":"bridge","outro":"outro"}[name]
    bar_idx = int((t - s) / BAR)
    prog = PROG[key]
    return CHORDS[prog[bar_idx % len(prog)]]

# ------------------------------------------------------------- note helpers
def note_midi(name):
    """'E4' -> 64, 'F#5' -> 78, 'Bb3' -> 58"""
    names = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,
             "Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
    if len(name) >= 2 and name[1] in "#b":
        pc, octv = names[name[:2]], int(name[2:])
    else:
        pc, octv = names[name[0]], int(name[1:])
    return (octv + 1) * 12 + pc

def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)

def parse_phrase(text):
    """'E4:1 G4:0.5 A4:2' -> [(midi, beats), ...]"""
    out = []
    for tok in text.split():
        n, d = tok.split(":")
        out.append((note_midi(n), float(d)))
    return out

def bars_to_notes(bar_patterns, total_beats):
    """Tile a list of 4-beat bar patterns (strings) over total_beats.
    Returns [(start_beat, dur_beats, midi)]."""
    notes = []
    t = 0.0
    i = 0
    while t < total_beats - 1e-6:
        pat = bar_patterns[i % len(bar_patterns)]
        for midi, d in parse_phrase(pat):
            if t >= total_beats - 1e-6:
                break
            d = min(d, total_beats - t)
            notes.append((t, d, midi))
            t += d
        i += 1
    return notes

# ------------------------------------------------------- vocal melodies
# bar patterns (4 beats each) per vocal section
VOCAL_MELODY = {
 "verse1": [
   "E4:1 G4:1 A4:1 B4:1",
   "A4:2 G4:1 E4:1",
   "G4:1 A4:1 B4:1 D5:1",
   "B4:2 A4:1 G4:1",
   "E4:1 G4:1 A4:1 B4:1",
   "D5:2 B4:1 A4:1",
   "G4:2 E4:2",
   "A4:1 B4:1 D5:1 B4:1",
 ],
 "pre1": [
   "C5:1 C5:1 D5:1 E5:1",
   "E5:2 D5:1 C5:1",
   "B4:1 C5:1 D5:1 E5:1",
   "E5:2 D5:2",
 ],
 "chorus": [
   "E4:1 G4:1 A4:1 B4:1",
   "D5:2 B4:1 A4:1",
   "G4:2 A4:1 B4:1",
   "A4:2 G4:2",
   "E4:1 G4:1 A4:1 B4:1",
   "D5:1 E5:1 D5:1 B4:1",
   "G4:2 E4:2",
   "E5:2 D5:1 C5:1",
 ],
 "verse2": [
   "E4:1 E4:1 G4:1 A4:1",
   "B4:2 A4:1 G4:1",
   "G4:1 A4:1 B4:1 D5:1",
   "D5:2 B4:2",
   "E4:1 G4:1 A4:1 B4:1",
   "A4:2 G4:1 E4:1",
   "G4:2 A4:2",
   "B4:2 D5:2",
 ],
 "bridge": [
   "E4:2 G4:1 A4:1",
   "B4:2 D5:1 C5:1",
   "C5:1 D5:1 E5:1 G5:1",
   "E5:2 D5:1 C5:1",
   "A4:2 G4:2",
   "B4:2 A4:2",
   "G4:2 B4:1 D5:1",
   "E5:4",
 ],
 "chorus3": [
   "E4:1 G4:1 A4:1 B4:1",
   "D5:2 B4:1 A4:1",
   "G4:2 A4:1 B4:1",
   "A4:2 G4:2",
   "E4:1 G4:1 A4:1 B4:1",
   "D5:1 E5:1 G5:1 E5:1",
   "G5:2 E5:2",
   "E5:1 G5:1 A5:1 B5:1",
   "G5:2 E5:2",
   "E5:4",
 ],
 "outro": [
   "E4:2 G4:2",
   "A4:2 B4:2",
   "G4:2 E4:2",
   "E4:4",
 ],
}

# ------------------------------------------------- instrumental melodies
# intro lead guitar (clean, delayed) - 8th-note feel
INTRO_LEAD = (
 "E5:0.5 G5:0.5 A5:1 B5:1 A5:0.5 G5:0.5 E5:1 D5:1 "
 "E5:0.5 G5:0.5 A5:1 G5:1 E5:2 "
 "C5:0.5 E5:0.5 G5:1 A5:1 G5:0.5 E5:0.5 D5:1 B4:1 "
 "E5:2 D5:1 C5:1 B4:2 "
 "E5:0.5 G5:0.5 A5:1 B5:1 A5:0.5 G5:0.5 E5:1 D5:1 "
 "E5:4 G4:2 A4:2"
)

# guitar solo (E minor pentatonic licks, 19 bars ~ 84 beats)
SOLO_LEAD = (
 "E5:0.5 G5:0.5 A5:1 B5:1 A5:0.5 G5:0.5 E5:0.5 D5:0.5 "
 "E5:1 G5:1 A5:2 B5:1 A5:1 "
 "G5:0.5 A5:0.5 B5:1 D6:1 B5:1 A5:1 G5:1 E5:1 "
 "D5:0.5 E5:0.5 G5:1 E5:1 D5:1 B4:1 G4:1 E4:1 "
 "E5:0.5 G5:0.5 A5:1 B5:1 D6:1 B5:1 A5:1 G5:1 "
 "E5:1 G5:1 A5:1 B5:1 A5:0.5 G5:0.5 E5:2 "
 "G5:0.5 A5:0.5 B5:0.5 D6:0.5 E6:1 D6:1 B5:1 "
 "A5:1 G5:1 E5:1 D5:1 E5:2 "
 "E5:0.5 G5:0.5 A5:1 B5:1 A5:0.5 G5:0.5 E5:0.5 D5:0.5 "
 "E5:2 G5:1 A5:1 B5:2 "
 "D6:1 B5:1 A5:1 G5:1 E5:1 G5:1 A5:2 "
 "B5:0.5 A5:0.5 G5:0.5 E5:0.5 D5:1 E5:2 "
 "G5:1 A5:1 B5:1 D6:1 E6:2 E6:2"
)

# outro lead (reprise of intro hook, softer)
OUTRO_LEAD = (
 "E5:1 G5:1 A5:2 B5:2 "
 "A5:1 G5:1 E5:2 D5:2 "
 "E5:1 G5:1 A5:2 G5:2 "
 "E5:4 E4:2 G4:2 "
 "E5:2 G5:1 A5:1 B5:2 "
 "E5:8"
)

# --------------------------------------------------- music-video schedule
# Each scene: image file (under media/work/scenes/), timeline slot, camera move,
# grade and overlay. Durations sum exactly to DURATION seconds.
SCENES = [
 dict(id="s01", file="s01_stage_wide.jpg",      start=0.0,   end=8.0,   move="push_in",  grade="blue_gold", overlay="haze"),
 dict(id="s02", file="s02_city_rain.jpg",       start=8.0,   end=20.0,  move="pan",      grade="blue",      overlay="rain"),
 dict(id="s03", file="s03_singer_stage.jpg",    start=20.0,  end=35.0,  move="push_in",  grade="blue_gold", overlay="haze"),
 dict(id="s04", file="s04_face_closeup.jpg",    start=35.0,  end=50.0,  move="slow_zoom",grade="blue",      overlay="none"),
 dict(id="s05", file="s05_guitarist.jpg",       start=50.0,  end=57.0,  move="drift",    grade="gold",      overlay="sparks"),
 dict(id="s06", file="s06_drummer.jpg",         start=57.0,  end=65.0,  move="push_in",  grade="blue",      overlay="none"),
 dict(id="s07", file="s07_chorus_wide.jpg",     start=65.0,  end=78.0,  move="push_in",  grade="blue_gold", overlay="flash"),
 dict(id="s08", file="s08_singer_power.jpg",    start=78.0,  end=100.0, move="drift",    grade="blue_gold", overlay="flash"),
 dict(id="s09", file="s09_rooftop_rain.jpg",    start=100.0, end=115.0, move="pan",      grade="blue",      overlay="rain"),
 dict(id="s10", file="s10_emotional_close.jpg", start=115.0, end=130.0, move="slow_zoom",grade="blue",      overlay="none"),
 dict(id="s11", file="s11_chorus_sparks.jpg",   start=130.0, end=148.0, move="push_in",  grade="blue_gold", overlay="sparks"),
 dict(id="s12", file="s12_singer_silhouette.jpg",start=148.0,end=165.0, move="drift",    grade="gold",      overlay="haze"),
 dict(id="s13", file="s13_solo_hands.jpg",      start=165.0, end=182.0, move="push_in",  grade="gold",      overlay="sparks"),
 dict(id="s14", file="s14_singer_spotlight.jpg",start=182.0, end=200.0, move="slow_zoom",grade="blue",      overlay="haze"),
 dict(id="s15", file="s15_bridge_dark.jpg",     start=200.0, end=215.0, move="slow_zoom",grade="dark",      overlay="haze"),
 dict(id="s16", file="s16_bridge_smoke.jpg",    start=215.0, end=230.0, move="push_in",  grade="blue",      overlay="smoke"),
 dict(id="s17", file="s17_final_pyro.jpg",      start=230.0, end=252.0, move="push_in",  grade="blue_gold", overlay="flash_sparks"),
 dict(id="s18", file="s18_final_closeup.jpg",   start=252.0, end=275.0, move="drift",    grade="blue_gold", overlay="flash"),
 dict(id="s19", file="s19_outro_edge.jpg",      start=275.0, end=300.0, move="pull_out", grade="dark",      overlay="haze"),
 dict(id="s20", file="s20_final_spot.jpg",      start=300.0, end=330.0, move="slow_zoom",grade="dark",      overlay="none"),
]

# singer-consistency reference image used when generating singer scenes
SINGER_REF = "s00_singer_portrait.jpg"

if __name__ == "__main__":
    total = sum(e - s for s, e in [(x["start"], x["end"]) for x in SCENES])
    print("scenes total:", total, "song duration:", DURATION)
    for name, s, e, en, voc in SECTIONS:
        print(f"{name:8s} {s:6.1f}-{e:6.1f}  beats={ (e-s)/BEAT :6.1f}")
