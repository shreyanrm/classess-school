import { describe, it, expect, vi } from 'vitest';
import {
  vidyaChat,
  parseActions,
  specToInline,
  type VidyaChatRequest,
} from '../vidya';

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as unknown as Response;
}

const REQ: VidyaChatRequest = {
  messages: [{ role: 'user', text: 'where is the class' }],
  role: 'teacher',
};

describe('vidyaChat — transport + graceful degradation (never throws)', () => {
  it('returns text + parsed actions on a successful turn', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        text: 'Here is the read.',
        actions: [
          { type: 'navigate', target: '/insights', reason: 'the full picture lives here' },
          {
            type: 'render',
            spec: {
              kind: 'mastery',
              topic: 'Trigonometric Ratios',
              plainLanguage: 'you can do this with guidance',
              independent: false,
              revisionDue: false,
              observationCount: 6,
              dimensions: [{ label: 'Performance', level: 'growing' }],
            },
          },
        ],
      }),
    ) as unknown as typeof fetch;

    const res = await vidyaChat(REQ, '/api/vidya/chat', fetchImpl);
    expect(res.degraded).toBeFalsy();
    expect(res.text).toBe('Here is the read.');
    expect(res.actions).toHaveLength(2);

    const nav = res.actions.find((a) => a.type === 'navigate');
    expect(nav && nav.type === 'navigate' && nav.target).toBe('/insights');

    const render = res.actions.find((a) => a.type === 'render');
    expect(render && render.type === 'render' && render.spec.kind).toBe('mastery');
  });

  it('signals degraded on a 503 (no key) — never throws', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ degraded: true, reason: 'key-unset' }, false, 503),
    ) as unknown as typeof fetch;
    const res = await vidyaChat(REQ, '/api/vidya/chat', fetchImpl);
    expect(res.degraded).toBe(true);
    expect(res.reason).toBe('key-unset');
    expect(res.text).toBe('');
    expect(res.actions).toEqual([]);
  });

  it('signals degraded on an HTTP error body — never throws', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ degraded: true, reason: 'provider-error' }, false, 502),
    ) as unknown as typeof fetch;
    const res = await vidyaChat(REQ, '/api/vidya/chat', fetchImpl);
    expect(res.degraded).toBe(true);
    expect(res.reason).toBe('provider-error');
  });

  it('signals degraded on a network throw — never throws to the caller', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;
    const res = await vidyaChat(REQ, '/api/vidya/chat', fetchImpl);
    expect(res.degraded).toBe(true);
    expect(res.reason).toBe('network');
  });

  it('does not touch the network beyond the single injected fetch', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ text: 'ok', actions: [] }));
    await vidyaChat(REQ, '/api/vidya/chat', fetchImpl as unknown as typeof fetch);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});

describe('parseActions — defensive action parsing', () => {
  it('parses a navigate and a render action, dropping malformed entries', () => {
    const actions = parseActions([
      { type: 'navigate', target: '/teacher/assign', reason: 'review here' },
      { type: 'navigate', target: '/not-a-real-route' }, // dropped: unknown target
      { type: 'render', spec: { kind: 'draft', title: 'Quick check' } },
      { type: 'render', spec: { kind: 'mystery' } }, // dropped: unknown kind
      null,
      'garbage',
    ]);
    expect(actions).toHaveLength(2);

    const [nav, render] = actions;
    expect(nav && nav.type).toBe('navigate');
    expect(nav && nav.type === 'navigate' && nav.target).toBe('/teacher/assign');
    expect(nav && nav.type === 'navigate' && nav.reason).toBe('review here');

    expect(render && render.type).toBe('render');
    expect(render && render.type === 'render' && render.spec.kind).toBe('draft');
  });

  it('returns an empty list for a non-array', () => {
    expect(parseActions(undefined)).toEqual([]);
    expect(parseActions({})).toEqual([]);
  });
});

describe('specToInline — render spec maps to a calm inline card', () => {
  it('maps a mastery spec without exposing any raw number', () => {
    const card = specToInline({
      kind: 'mastery',
      topic: 'Trigonometric Ratios',
      plainLanguage: 'you can do this with guidance',
      independent: false,
      revisionDue: true,
      observationCount: 6,
      dimensions: [
        { label: 'Performance', level: 'growing' },
        { label: 'Reliability', level: 'strong' },
      ],
    });
    expect(card).not.toBeNull();
    expect(card!.title).toContain('Trigonometric Ratios');
    expect(card!.body).toBe('you can do this with guidance');
    // No digit anywhere in the learner-facing card.
    expect(/\d/.test(card!.title + card!.body + (card!.items ?? []).join(' '))).toBe(false);
  });

  it('maps a draft spec carrying its approval route', () => {
    const card = specToInline({
      kind: 'draft',
      title: 'Quick check — Fractions',
      topic: 'Fractions',
      body: 'Prepared for your review.',
      items: ['Two recall items'],
      confidence: 'middle',
      requiresApproval: true,
      openHref: '/teacher/assign',
      openLabel: 'Review and set live',
    });
    expect(card!.openHref).toBe('/teacher/assign');
    expect(card!.openLabel).toBe('Review and set live');
    expect(card!.confidence).toBe('middle');
  });
});
