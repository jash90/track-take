import pytest

from tracktake.lyrics import clean_line, kind_of, parse_lyrics, split_tag, sung_lines

EXCERPT = """\
[Short Instrumental Intro: Soft Piano, Distant Pad]
[Rain]
[Phone Static]

[Verse 1: Female Vocal, Soft and Intimate]
Your coat still hangs by the door,
Like it forgot what goodbye means.

The kitchen light is cold tonight,
Two empty cups, one shaking hand.

[Pre-Chorus: Building Tension, Breathier Vocal]
I tried to hate you,
But my heart would not learn.

[Build-Up]

[Chorus: Full Band, Powerful and Emotional]
And it hurts where the silence hurts,
In the room where we used to dance.

[Instrumental Break: Muted Electric Guitar, Deep Drums]

[Breakdown: Piano Only, Intimate]
[Female Whisper]
I keep the last good morning
Beside you...

[Bridge: Barely Controlled, Rising Strings]
Maybe someday I will thank you

[Silence]

[Final Chorus: Intense, Belting, Layered Choir]
And it hurts where the silence hurts,

[Outro: Soft Piano, Female Vocal Fading]
But now at least I know.

[Rain Fading]
[Fade Out]
"""


@pytest.fixture
def blocks():
    return parse_lyrics(EXCERPT)


def test_block_order_and_kinds(blocks):
    assert [(b.label, b.kind) for b in blocks] == [
        ("Short Instrumental Intro", "intro"),
        ("Verse 1", "verse"),
        ("Pre-Chorus", "pre_chorus"),
        ("Build-Up", "build"),
        ("Chorus", "chorus"),
        ("Instrumental Break", "break"),
        ("Breakdown", "breakdown"),
        ("Bridge", "bridge"),
        ("Silence", "break"),
        ("Final Chorus", "chorus"),
        ("Outro", "outro"),
    ]


def test_tag_details_and_lines(blocks):
    verse = blocks[1]
    assert verse.tag_details == "Female Vocal, Soft and Intimate"
    assert verse.lines == [
        "Your coat still hangs by the door,",
        "Like it forgot what goodbye means.",
        "The kitchen light is cold tonight,",
        "Two empty cups, one shaking hand.",
    ]
    assert blocks[3].tag_details == ""


def test_instrumental_blocks(blocks):
    instrumental = [b.label for b in blocks if b.instrumental]
    assert instrumental == ["Short Instrumental Intro", "Build-Up", "Instrumental Break", "Silence"]


def test_sound_effect_tags_become_hints(blocks):
    by_label = {b.label: b for b in blocks}
    assert by_label["Short Instrumental Intro"].hints == ["Rain", "Phone Static"]
    assert by_label["Breakdown"].hints == ["Female Whisper"]
    assert by_label["Breakdown"].lines == ["I keep the last good morning", "Beside you..."]
    assert by_label["Outro"].hints == ["Rain Fading", "Fade Out"]
    assert not any(b.label in {"Rain", "Phone Static", "Female Whisper", "Fade Out"} for b in blocks)


def test_sung_lines_keep_block_index(blocks):
    lines = sung_lines(blocks)
    assert lines[0] == (1, "Your coat still hangs by the door,")
    assert lines[-1] == (10, "But now at least I know.")
    assert len(lines) == 4 + 2 + 2 + 2 + 1 + 1 + 1


@pytest.mark.parametrize(
    ("label", "kind"),
    [
        ("Pre-Chorus", "pre_chorus"),
        ("Prechorus", "pre_chorus"),
        ("Post-Chorus", "chorus"),
        ("Final Chorus", "chorus"),
        ("Hook", "chorus"),
        ("Verse 2", "verse"),
        ("Build Up", "build"),
        ("Breakdown", "breakdown"),
        ("Instrumental Break", "break"),
        ("Guitar Solo", "break"),
        ("Interlude", "break"),
        ("Short Instrumental Intro", "intro"),
        ("Outro", "outro"),
        ("End", "outro"),
        ("Rain", None),
        ("Phone Static", None),
        ("Female Whisper", None),
        ("Fade Out", None),
    ],
)
def test_kind_of(label, kind):
    assert kind_of(label) == kind


def test_split_tag_and_clean_line():
    assert split_tag("Verse 1: Female Vocal, Soft") == ("Verse 1", "Female Vocal, Soft")
    assert split_tag("Build-Up") == ("Build-Up", "")
    assert clean_line("I keep [whisper] the  last ") == "I keep the last"


def test_untagged_lines_and_unknown_tag_with_lines():
    blocks = parse_lyrics("hello there\n\n[Silence]\n[Spoken Word]\nsay it\n")
    assert [(b.label, b.kind, b.lines) for b in blocks] == [
        ("", "other", ["hello there"]),
        ("Silence", "break", []),
        ("Spoken Word", "other", ["say it"]),
    ]


def test_leading_hint_moves_to_first_block():
    blocks = parse_lyrics("[Rain]\n[Intro]\n[Verse]\nla la\n")
    assert blocks[0].label == "Intro" and blocks[0].hints == ["Rain"]
