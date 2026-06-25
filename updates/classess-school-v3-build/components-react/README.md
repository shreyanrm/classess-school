# components-react · hero seeds

These are **reference React implementations of the hardest visual pieces** — the ones
with exact motion and feel that are easiest to get wrong from prose. They are extracted
from the runnable prototypes in `../prototype/` and are token-driven (import
`../design-system/tokens.css` once at the app root). Port the rest of the component
library (`../10-component-library.md`) to React the same way; these set the bar.

| File | What it is | Spec |
|---|---|---|
| `VidyaOrb.jsx` | The living floating presence (drift + breathe); opens voice mode. | `17.1` |
| `VoiceBloom.jsx` | The Siri-like voice overlay — flowing warm canvas bloom, masked + blurred. | `17.2` |
| `CommandPalette.jsx` | The universal Cmd/Ctrl-K launcher (search · jump · ask · voice). | `17.3` |
| `ExpandingRail.jsx` | The thin rail that expands butter-smooth on hover / pin. | `18.1` |
| `ConversationHome.jsx` | The conversation-first home (greeting · composer · chips · ambient bloom). | `16.1` |
| `GenerativeSurface.jsx` | The Path-2 pattern — a component takes shape (border-draw + grow). | `16.2` |
| `CrystallizeNode.jsx` | The signature mastery moment (variants a/b/c) — replaces ignite. | `17.5`, `20.2` |

## Notes for Claude Code

- **Tokens, never hardcode.** Every colour/space/radius/motion value is a `var(--token)`
  from `design-system/tokens.css`. The inline `<style>` blocks here exist so each seed is
  self-contained and reviewable; in the app, lift them into the component layer / CSS
  modules and keep the class contracts.
- **No shadows.** Depth is hairline + tonal step + frost only. If you reach for a shadow,
  stop.
- **Reduced-motion** is handled in each seed; preserve it.
- **Wire the real systems:** `VoiceBloom` simulates nothing about audio — connect it to the
  STT path in the AI fabric (`11`); `CommandPalette` takes a `commands` registry (routes +
  actions + a Vidya fallback); `CrystallizeNode` fires on a genuine `mastery.updated` →
  independent event, never on routine completion.
- **These are starting points, not the whole app.** Compose them into the shell (`18`),
  feed them governed data through the gateway (`03`, `12`), and build the remaining
  surfaces and components from the specs.
