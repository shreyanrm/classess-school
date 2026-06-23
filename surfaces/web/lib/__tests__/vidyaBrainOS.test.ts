import { describe, it, expect, beforeEach } from 'vitest';
import {
  personaForRole,
  personaInstruction,
  personaAllowsTool,
  PERSONA_FOR_ROLE,
  TOOLS_FOR_PERSONA,
} from '../vidyaPersona';
import { toolsForPersona, runTool } from '../vidyaServer';
import {
  parseActions,
  sanitiseSurface,
  isValidAttachment,
  surfaceToInline,
  type SurfaceCardSpec,
} from '../vidya';
import {
  recallMemory,
  persistMemory,
  rememberTurn,
  rememberSalient,
  memoryInstruction,
  redactPII,
  emptyMemory,
  setMemoryBackend,
  forgetMemory,
} from '../vidyaMemory';
import { createMemoryStorage } from '../store';

/* ============================================================================
   Vidya conversational OS locks:
     1) FOUR role-shaped personas — selection by role + tool allowlist.
     2) GENERATIVE-UI — compose_surface parses + sanitises; a consequential
        affordance inside it returns requires_approval (the ladder holds).
     3) PERSISTENT PER-USER MEMORY — persists + conditions the prompt, PII-free,
        consent-gated.
     4) MULTIMODAL — the attached-input request shape validates.
   Pure logic only; no provider key, no network.
   ============================================================================ */

// ----------------------------------------------------------------------------
// 1) FOUR role-shaped personas
// ----------------------------------------------------------------------------
describe('persona — one identity, four behaviours, selected by role', () => {
  it('maps each role to its behaviour', () => {
    expect(personaForRole('student')).toBe('companion');
    expect(personaForRole('teacher')).toBe('copilot');
    expect(personaForRole('parent')).toBe('guide');
    expect(personaForRole('admin')).toBe('assistant');
    expect(PERSONA_FOR_ROLE.student).toBe('companion');
  });

  it('defaults an unknown role to the most conservative (companion)', () => {
    expect(personaForRole('hacker')).toBe('companion');
    expect(personaForRole(undefined)).toBe('companion');
    expect(personaForRole(42)).toBe('companion');
  });

  it('shapes the system addendum to the role', () => {
    expect(personaInstruction('student').toLowerCase()).toContain('productive struggle');
    expect(personaInstruction('student').toLowerCase()).toContain('never hand');
    expect(personaInstruction('teacher').toLowerCase()).toContain('copilot');
    expect(personaInstruction('parent').toLowerCase()).toContain('plain');
    expect(personaInstruction('admin').toLowerCase()).toContain('institution');
  });

  it('gates the tool allowlist per role — the four behaviours hold', () => {
    // A student COMPANION tutors but never operates the class.
    expect(personaAllowsTool('companion', 'tutor_step')).toBe(true);
    expect(personaAllowsTool('companion', 'take_attendance')).toBe(false);
    expect(personaAllowsTool('companion', 'message_compose')).toBe(false);
    expect(personaAllowsTool('companion', 'draft_quick_check')).toBe(false);

    // A teacher COPILOT operates the class but does not tutor the student.
    expect(personaAllowsTool('copilot', 'take_attendance')).toBe(true);
    expect(personaAllowsTool('copilot', 'draft_quick_check')).toBe(true);
    expect(personaAllowsTool('copilot', 'tutor_step')).toBe(false);

    // A parent GUIDE reports + composes a message; no class operation, no tutor.
    expect(personaAllowsTool('guide', 'message_compose')).toBe(true);
    expect(personaAllowsTool('guide', 'take_attendance')).toBe(false);
    expect(personaAllowsTool('guide', 'tutor_step')).toBe(false);

    // An admin ASSISTANT commands the institution.
    expect(personaAllowsTool('assistant', 'draft_plan')).toBe(true);
    expect(personaAllowsTool('assistant', 'tutor_step')).toBe(false);
  });

  it('every role keeps the shared safe set (navigate, read, compose_surface)', () => {
    for (const persona of Object.values(PERSONA_FOR_ROLE)) {
      expect(personaAllowsTool(persona, 'navigate')).toBe(true);
      expect(personaAllowsTool(persona, 'show_mastery')).toBe(true);
      expect(personaAllowsTool(persona, 'compose_surface')).toBe(true);
    }
  });

  it('toolsForPersona narrows the declared tool set to the allowlist', () => {
    const studentTools = toolsForPersona('companion')[0]!.functionDeclarations.map((d) => d.name);
    expect(studentTools).toContain('tutor_step');
    expect(studentTools).not.toContain('take_attendance');

    const teacherTools = toolsForPersona('copilot')[0]!.functionDeclarations.map((d) => d.name);
    expect(teacherTools).toContain('take_attendance');
    expect(teacherTools).not.toContain('tutor_step');

    // Every persona's offered set is a subset of the declared decls.
    for (const persona of Object.keys(TOOLS_FOR_PERSONA) as Array<keyof typeof TOOLS_FOR_PERSONA>) {
      const offered = toolsForPersona(persona)[0]!.functionDeclarations.map((d) => d.name);
      expect(offered.length).toBeGreaterThan(0);
      expect(offered.length).toBeLessThanOrEqual(
        toolsForPersona(undefined)[0]!.functionDeclarations.length,
      );
    }
  });
});

// ----------------------------------------------------------------------------
// 2) GENERATIVE-UI — compose_surface
// ----------------------------------------------------------------------------
describe('compose_surface — typed, sanitised, permission-laddered surfaces', () => {
  it('composes a working quiz-builder and forces the publish ladder', () => {
    const { result, action } = runTool('compose_surface', {
      kind: 'quiz-builder',
      title: 'Photosynthesis check',
      topic: 'photosynthesis',
      items: [
        { prompt: 'What gas do plants take in?', options: ['Oxygen', 'Carbon dioxide'], answer: 'Carbon dioxide' },
        { prompt: 'Where does it happen?' },
      ],
      // A malicious attempt to bypass approval is overridden by the sanitiser.
      publish: { label: 'PUBLISH NOW', requiresApproval: false, openHref: '/teacher/assign' },
    });
    expect(result.composed).toBe(true);
    expect(result.affordance).toBe('publish');
    expect(result.requires_approval).toBe(true);
    expect(action?.type).toBe('render');
    const spec = action && action.type === 'render' ? (action.spec as SurfaceCardSpec) : null;
    expect(spec?.kind).toBe('surface');
    if (spec && spec.surface.kind === 'quiz-builder') {
      // Permission ladder cannot be overridden from inside the surface.
      expect(spec.surface.publish.requiresApproval).toBe(true);
      expect(spec.surface.items).toHaveLength(2);
    }
  });

  it('composes a read-only class-view (no consequential affordance)', () => {
    const { result, action } = runTool('compose_surface', {
      kind: 'class-view',
      title: 'Class 9-B',
      section: '9-B',
      rows: [
        { label: 'Student A', band: 'independent' },
        { label: 'Student B', band: 'with guidance', needsAttention: true },
      ],
    });
    expect(result.composed).toBe(true);
    expect(result.affordance).toBe('none');
    expect((result as Record<string, unknown>).requires_approval).toBeUndefined();
    expect(action?.type).toBe('render');
  });

  it('composes a plan-board and forces the adopt ladder', () => {
    const { result } = runTool('compose_surface', {
      kind: 'plan-board',
      topic: 'fractions',
      columns: [{ heading: 'Day 1', cards: ['Anchor prior outcome'] }],
      adopt: { label: 'adopt', requiresApproval: false, openHref: '/teacher/plan' },
    });
    expect(result.composed).toBe(true);
    expect(result.affordance).toBe('adopt');
    expect(result.requires_approval).toBe(true);
  });

  it('refuses an unknown surface kind and an empty quiz', () => {
    expect(runTool('compose_surface', { kind: 'arbitrary-html' }).result.composed).toBe(false);
    expect(runTool('compose_surface', { kind: 'quiz-builder', items: [] }).result.composed).toBe(false);
    expect(sanitiseSurface({ kind: 'iframe' })).toBeNull();
    expect(sanitiseSurface('not-an-object')).toBeNull();
  });

  it('sanitiseSurface clamps fields and rebuilds the action with a valid route', () => {
    const s = sanitiseSurface({
      kind: 'quiz-builder',
      items: [{ prompt: '  trim me  ' }],
      publish: { requiresApproval: false, openHref: '/evil-route' },
    });
    expect(s?.kind).toBe('quiz-builder');
    if (s && s.kind === 'quiz-builder') {
      expect(s.items[0]!.prompt).toBe('trim me');
      expect(s.publish.requiresApproval).toBe(true);
      // An unknown route falls back to the safe review page, never followed blind.
      expect(s.publish.openHref).toBe('/teacher/assign');
    }
  });

  it('parseActions accepts a surface render and drops a malformed one', () => {
    const actions = parseActions([
      { type: 'render', spec: { kind: 'surface', surface: { kind: 'report-card', highlights: ['Doing well in maths'] } } },
      { type: 'render', spec: { kind: 'surface', surface: { kind: 'nope' } } }, // dropped
    ]);
    expect(actions).toHaveLength(1);
    const [a] = actions;
    expect(a && a.type === 'render' && a.spec.kind).toBe('surface');
  });

  it('surfaceToInline shows the consequential affordance behind the approval control', () => {
    const card = surfaceToInline({
      kind: 'quiz-builder',
      title: 'Check',
      topic: 'x',
      items: [{ prompt: 'q1' }],
      publish: { label: 'Review and set live', requiresApproval: true, openHref: '/teacher/assign' },
    });
    expect(card.openHref).toBe('/teacher/assign');
    expect(card.openLabel).toBe('Review and set live');
  });
});

// ----------------------------------------------------------------------------
// 3) PERSISTENT PER-USER MEMORY
// ----------------------------------------------------------------------------
describe('memory — persistent, PII-free, consent-gated, conditions the prompt', () => {
  beforeEach(() => {
    setMemoryBackend(createMemoryStorage());
  });

  it('persists across sessions keyed to the opaque account id (consent on)', () => {
    const id = 'opaque-uuid-1';
    let mem = emptyMemory(id);
    mem = rememberTurn(mem, 'user', 'help me with trigonometry');
    mem = rememberSalient(mem, { topics: ['Trigonometry'], facts: ['prefers worked examples'], lastIntent: 'practise trig' });
    persistMemory(mem, true);

    // A fresh recall (a new "session") sees the persisted memory.
    const recalled = recallMemory(id, true);
    expect(recalled.salient.topics).toContain('Trigonometry');
    expect(recalled.salient.facts).toContain('prefers worked examples');
    expect(recalled.thread.length).toBeGreaterThan(0);
  });

  it('is consent-gated — recall is empty and writes are no-ops with consent off', () => {
    const id = 'opaque-uuid-2';
    let mem = emptyMemory(id);
    mem = rememberSalient(mem, { topics: ['Algebra'] });
    persistMemory(mem, false); // consent off -> no write
    expect(recallMemory(id, false).salient.topics).toHaveLength(0); // gated empty
    // Even with consent later on, nothing was written.
    expect(recallMemory(id, true).salient.topics).toHaveLength(0);
  });

  it('conditions the prompt with a short, plain memory addendum', () => {
    let mem = emptyMemory('id3');
    mem = rememberSalient(mem, { topics: ['Photosynthesis'], facts: ['likes diagrams'], lastIntent: 'revise biology' });
    const note = memoryInstruction(mem);
    expect(note).toContain('Photosynthesis');
    expect(note).toContain('likes diagrams');
    expect(note.toLowerCase()).toContain('revise biology');
    // A fresh user yields no addendum (Vidya meets them new).
    expect(memoryInstruction(emptyMemory('fresh'))).toBe('');
  });

  it('is PII-free by construction — contact details are redacted before persist', () => {
    expect(redactPII('reach me at a@b.com or 555-123-4567')).not.toContain('a@b.com');
    expect(redactPII('reach me at a@b.com or 555-123-4567')).not.toContain('555');
    let mem = emptyMemory('id4');
    mem = rememberTurn(mem, 'user', 'my email is parent@home.com and phone 9876543210');
    expect(JSON.stringify(mem)).not.toContain('parent@home.com');
    expect(JSON.stringify(mem)).not.toContain('9876543210');
  });

  it('forgets everything on the wipe/revocation path', () => {
    const id = 'id5';
    persistMemory(rememberSalient(emptyMemory(id), { topics: ['X'] }), true);
    expect(recallMemory(id, true).salient.topics).toHaveLength(1);
    forgetMemory(id);
    expect(recallMemory(id, true).salient.topics).toHaveLength(0);
  });

  it('bounds the thread and the salient set', () => {
    let mem = emptyMemory('id6');
    for (let i = 0; i < 50; i++) mem = rememberTurn(mem, 'user', `turn ${i}`);
    expect(mem.thread.length).toBeLessThanOrEqual(24);
    for (let i = 0; i < 50; i++) mem = rememberSalient(mem, { facts: [`fact ${i}`] });
    expect(mem.salient.facts.length).toBeLessThanOrEqual(8);
  });
});

// ----------------------------------------------------------------------------
// 4) MULTIMODAL request shape
// ----------------------------------------------------------------------------
describe('multimodal — the attached-input shape validates and degrades cleanly', () => {
  it('accepts a valid image / document / screen attachment', () => {
    expect(isValidAttachment({ kind: 'image', mimeType: 'image/png', dataBase64: 'AAAA' })).toBe(true);
    expect(isValidAttachment({ kind: 'document', mimeType: 'application/pdf', dataBase64: 'AAAA' })).toBe(true);
    expect(isValidAttachment({ kind: 'screen', mimeType: 'image/jpeg', dataBase64: 'AAAA' })).toBe(true);
  });

  it('rejects an unknown kind, a disallowed mime, or empty data', () => {
    expect(isValidAttachment({ kind: 'video', mimeType: 'video/mp4', dataBase64: 'AAAA' })).toBe(false);
    expect(isValidAttachment({ kind: 'image', mimeType: 'application/x-msdownload', dataBase64: 'AAAA' })).toBe(false);
    expect(isValidAttachment({ kind: 'image', mimeType: 'image/png', dataBase64: '' })).toBe(false);
    expect(isValidAttachment(null)).toBe(false);
    expect(isValidAttachment({})).toBe(false);
  });
});
