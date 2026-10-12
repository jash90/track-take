"""How a video moves: the shot rhythm, the camera language and the montage, independent of how it looks.

- stopmotion: continuous takes that flow into each other, the montage samples the clips "on twos" (a new drawing
  every 2 frames and on every beat), the camera pumps on downbeats and shakes on snares, a slow push-in per take.
- tableau ("living illustration"), modelled on the rhythm of animated videos like Taco Hemingway's "Deszcz na
  betonie" (45 transitions in 4:12, a change every ~5.2 s): every shot is its own calm, almost still illustration
  where only small things move, the camera locked or drifting sideways with parallax; the montage plays the clips
  smoothly. The rhythm follows the song's parts:
  - intro: one long sideways travelling shot (up to 20 s) that reveals the place piece by piece;
  - verses and other parts: tableaux of ~5.2 s chained by quick whip pans (motion-blurred slide, ~0.4 s);
  - choruses (and the outro): hard cuts on the bar, alternating a short insert (~2.6 s close-up detail) and a long
    wide shot (~7.7 s);
  - every part starts on a hard cut.
"""

from __future__ import annotations

ANIMATIONS: dict[str, dict] = {
    "stopmotion": {
        "name": {"pl": "Poklatkowa", "en": "Stop-motion"},
        "takes": True,  # shots may continue each other (one camera take over several shots)
        "min_shot_s": 5.0,  # shots are 2 bars, doubled until at least this long
        "cadence": 2,  # output frames per drawing
        "beat_motion": True,
        "zoom": 0.04,  # push-in over a take
        "whip_frames": 0,
        "motion": "",
    },
    "tableau": {
        "name": {"pl": "Żywa ilustracja", "en": "Living illustration"},
        "takes": False,
        "min_shot_s": 4.0,
        "cadence": 1,
        "beat_motion": False,
        "zoom": 0.0,
        "whip_frames": 5,  # frames of the whip on each side of the cut
        # rhythm per song part: shot lengths in seconds (rounded to whole bars) and how shots of the part are joined
        "travel_max_s": 20.0,
        "tableau_s": 5.2,
        "insert_s": 2.6,
        "wide_s": 7.7,
        "cut_parts": ("intro", "chorus", "outro"),
        "motion": (
            "Animation style - living illustration: every shot is its own calm tableau, like a moving painting. "
            "The camera is locked off, or drifts slowly sideways (left to right) with layered parallax: dark "
            "foreground silhouettes (leaves, branches, posts, a window frame) slide past faster than the background. "
            "Only small things move: a train crossing far away, a figure turning a page or walking a few steps, "
            "smoke, birds, water ripples, flickering lights, curtains, rain. No camera moves towards or around the "
            "subject, no zooms, no big actions, no running or dancing. Prefer wide and medium shots of places with "
            "small figures; every `motion` names one slow sideways drift or a locked camera plus one or two small "
            "movements in the scene. Frame each shot so a foreground silhouette sits at one edge (it helps the "
            "quick sideways transitions between shots). Each shot has a role: `travel` - a long sideways tracking "
            "shot that crosses a long scene (a train, a street, a row of houses) and reveals it piece by piece; "
            "`insert` - a ~2 s close-up detail (hands, an object, a light, a face in profile), almost still; `wide` - "
            "a wide establishing tableau of a place with small figures; `tableau` - a calm medium or wide picture."
        ),
    },
}
DEFAULT = "stopmotion"


def get(name: str | None) -> dict:
    return ANIMATIONS.get(name or DEFAULT, ANIMATIONS[DEFAULT])


def listing() -> list[dict]:
    return [{"id": k, "name": v["name"]} for k, v in ANIMATIONS.items()]
