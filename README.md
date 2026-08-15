# Spell Quest

Two applications. They share photos and audio, and nothing else.

```
live-game/            the game a six-year-old plays every day  ← in use
adaptive-platform/    the adaptive learning platform being built  ← local only
tools/                how the photos and voice clips were generated
CLAUDE.md             briefing for a new Claude Code session
```

| | Live game | Adaptive platform |
|---|---|---|
| Where | https://nirmalkumargcp-ux.github.io/spell-quest/ | `http://127.0.0.1:8010/app/` |
| Status | **Published and in daily use** | Built and tested, not deployed |
| Start here | [`live-game/README.md`](live-game/README.md) | [`adaptive-platform/README.md`](adaptive-platform/README.md) |

## The one rule

`live-game/` **is** the website. A push that touches it reaches the child
within a couple of minutes. Build the platform alongside; switch over
deliberately, not by accident.

## Shared assets

`live-game/images/` and `live-game/audio/` are used by both apps. The platform
reads them from there; point `ASSETS_ROOT` elsewhere if you ever separate them.
They stay with the live game because that app must be able to ship on its own.
