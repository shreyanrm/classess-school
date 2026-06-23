import { describe, it, expect } from 'vitest';
import { SYSTEM, TOOLS, runTool } from '../vidyaServer';
import { isNavTarget } from '../vidya';

/* ============================================================================
   Cheap locks on the Vidya server core: the persona biases toward acting, the
   navigate tool exposes the full route enum, and the permission ladder holds
   (consequential tools only ever PREPARE — they never auto-fire).
   ============================================================================ */

describe('Vidya SYSTEM persona', () => {
  it('biases toward navigating/acting on actionable intent', () => {
    expect(SYSTEM.toLowerCase()).toContain('navigation is a first-class action');
    expect(SYSTEM.toLowerCase()).toContain('bias toward');
  });

  it('encodes the key colloquial intent mappings the brief calls out', () => {
    const s = SYSTEM.toLowerCase();
    expect(s).toContain('/student/progress');
    expect(s).toContain('/admin/setup');
    expect(s).toContain('take_attendance');
    expect(s).toContain('draft_quick_check');
    expect(s).toContain('start_live_class');
  });

  it('keeps the permission-ladder language (never auto-send/grade/submit)', () => {
    const s = SYSTEM.toLowerCase();
    expect(s).toContain('never done');
    expect(s).toMatch(/grad|submit|send/);
  });

  it('keeps the no-emoji, no-exclamation, no-raw-number rules', () => {
    expect(SYSTEM).toContain('Never use emoji or exclamation marks');
    expect(SYSTEM.toLowerCase()).toContain('never');
  });

  it('drives the full capability set from natural language, not just navigation', () => {
    const s = SYSTEM.toLowerCase();
    for (const cap of ['tutor', 'explain', 'create', 'assess', 'answer', 'navigate']) {
      expect(s).toContain(cap);
    }
  });

  it('encodes the speak-and-show contract (highlight / annotate / steps)', () => {
    const s = SYSTEM.toLowerCase();
    expect(s).toContain('speak and show');
    expect(s).toContain('highlight_target');
    expect(s).toContain('annotate_target');
    expect(s).toContain('explain_steps');
  });

  it('tutor guidance never explains first', () => {
    expect(SYSTEM.toLowerCase()).toContain('never explain first');
  });
});

describe('Vidya tool surface — the new capabilities are declared', () => {
  function toolNames(): string[] {
    return TOOLS[0]!.functionDeclarations.map((d) => d.name);
  }
  it('exposes the new capability tools', () => {
    const names = toolNames();
    for (const t of ['tutor_step', 'explain_steps', 'highlight_target', 'annotate_target', 'create_study_plan']) {
      expect(names).toContain(t);
    }
  });
  it('highlight_target enum matches the closed region map', () => {
    const decls = TOOLS[0]!.functionDeclarations;
    const hl = decls.find((d) => d.name === 'highlight_target');
    const en = (hl?.parameters?.properties?.region as { enum?: string[] } | undefined)?.enum ?? [];
    expect(en.length).toBeGreaterThan(3);
    expect(en).toContain('mastery-band');
  });
});

describe('Vidya navigate tool', () => {
  function navEnum(): string[] {
    const decls = TOOLS[0]!.functionDeclarations;
    const nav = decls.find((d) => d.name === 'navigate');
    return (nav?.parameters?.properties?.target as { enum?: string[] } | undefined)?.enum ?? [];
  }

  it('exposes a target enum that the route guard accepts in full', () => {
    const en = navEnum();
    expect(en.length).toBeGreaterThan(20);
    for (const t of en) expect(isNavTarget(t)).toBe(true);
  });

  it('includes home and the role landing destinations', () => {
    const en = navEnum();
    expect(en).toContain('/');
    expect(en).toContain('/student/progress');
    expect(en).toContain('/admin/setup');
  });
});

describe('permission ladder — consequential tools only prepare', () => {
  it('draft_quick_check requires approval and never publishes', () => {
    const { result } = runTool('draft_quick_check', { topic: 'Fractions' });
    expect(result.requires_approval).toBe(true);
    expect(result.prepared).toBe(true);
  });

  it('message_compose prepares a draft and requires approval (never sends)', () => {
    const { result } = runTool('message_compose', { topic: 'attendance' });
    expect(result.requires_approval).toBe(true);
    expect(result.prepared).toBe(true);
  });

  it('take_attendance proposes; the teacher confirms (a navigate directive)', () => {
    const { action } = runTool('take_attendance', {});
    expect(action?.type).toBe('navigate');
    expect(action && action.type === 'navigate' && action.target).toBe('/teacher/attendance');
  });

  it('navigate drops an unknown destination', () => {
    const { action, result } = runTool('navigate', { target: '/nope' });
    expect(action).toBeUndefined();
    expect(result.navigated).toBe(false);
  });
});
