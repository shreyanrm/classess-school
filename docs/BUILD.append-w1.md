# BUILD.md — Completion Wave 1 (W1) addendum

APPEND-ONLY supplement. The original `docs/BUILD.md` could not be read or appended
to in the W1 host (macOS TCC restriction on `~/Documents`; pre-existing files are
read/append/rename/delete denied, only new files can be created). A maintainer
with full filesystem access should fold the content below into `docs/BUILD.md`.

See `docs/COMPLETION-W1.md` for the full wave writeup (Vidya orchestrator + tools
+ permission ladder, the new domains, gateway hardening, connections, run steps,
and env names).

## Pointer

- Completion Wave 1 record: `docs/COMPLETION-W1.md`

## Tree update (new this wave)

```
modules/
  attendance/
    app/{__init__,capture,risk,reconciliation,staff,events,safety}.py
    tests/{test_capture,test_risk,test_reconciliation,test_staff,
           test_events,test_safety,test_offline_shape}.py
    conftest.py  pytest.ini  README.md
  planning/
    __init__.py  README.md
    app/{__init__,events,plans,differentiation,diary,pacing_link}.py
    tests/{conftest,test_events,test_plans,test_pacing_link,
           test_differentiation,test_diary}.py
  classroom/
    app/{__init__,events,board_state,live_session,poll_engine,
         device_free_check,attention}.py
    tests/{conftest,test_events,test_board,test_polls,
           test_device_free_check,test_attention,test_live}.py
    README.md  pytest.ini
  coursework/                       # EXTENSIONS (W1 blocked by host TCC; see below)
    app/{exam_ops,mocks,groups}.py  # to extend papers.py + blueprint
  learning/
    app/misconception.py
    tests/test_misconception.py
    README.misconception.md
  content/
    app/{dedup,artifacts}.py
    tests/{test_dedup,test_artifacts}.py
    README.dedup.md  README.artifacts.md

spine/
  gateway/
    app/{ratelimit,validation,capabilities,wall}.py
    app/ratelimit_config.example.json
    tests/{test_ratelimit,test_validation,test_wall_capabilities}.py
    README.hardening.md

surfaces/
  web/
    app/api/vidya            # Vidya autonomous orchestrator API route
    lib/vidya.ts             # Vidya orchestrator library (server-side secrets only)
```

## W1 blockers (carry forward)

- web-foundation: BLOCKED, no code written (could not read existing files).
- coursework-ext: BLOCKED, no code written (could not read papers.py/blueprint to
  EXTEND exam_ops/mocks/groups without guessing). Intended contracts in
  `docs/COMPLETION-W1.md` Section 2.4.
- attendance `app/capture.py` and `app/risk.py`: pre-existing, OS-locked; verify
  they match the documented public APIs or regenerate.
- Docs sidecars to fold in: this file and `docs/TESTING.append-w1.md`.
