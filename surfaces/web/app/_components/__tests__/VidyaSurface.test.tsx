import { describe, it, expect, afterEach, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { VidyaSurface } from '../VidyaSurface';
import type {
  QuizBuilderSurface,
  ClassViewSurface,
  PlanBoardSurface,
  ReportCardSurface,
} from '@/lib/vidya';

afterEach(cleanup);

/* ============================================================================
   The OPERABLE generative surface rendered inline in the orb conversation. It
   must be a real, interactive panel (not a flat card), and the PERMISSION LADDER
   must hold: a consequential affordance (publish a quiz, adopt a plan) never
   fires — it only PREPARES and routes the human to review.
   ============================================================================ */

const quiz: QuizBuilderSurface = {
  kind: 'quiz-builder',
  title: 'Photosynthesis quick check',
  topic: 'photosynthesis',
  items: [
    { prompt: 'What gas do plants take in?', options: ['Oxygen', 'Carbon dioxide'], answer: 'Carbon dioxide' },
    { prompt: 'Where does it happen?' },
  ],
  publish: { label: 'Review and set live', requiresApproval: true, openHref: '/teacher/assign' },
};

describe('VidyaSurface — quiz-builder (operable, permission-laddered)', () => {
  it('renders editable question inputs (a real interactive surface, not a flat card)', () => {
    render(<VidyaSurface spec={quiz} />);
    expect(screen.getByTestId('vidya-surface')).toHaveAttribute('data-surface-kind', 'quiz-builder');
    const inputs = screen.getAllByTestId('vidya-surface-item-input') as HTMLInputElement[];
    expect(inputs).toHaveLength(2);
    expect(inputs[0]?.value).toBe('What gas do plants take in?');

    // Editing a question updates the working copy in place.
    fireEvent.change(inputs[0]!, { target: { value: 'Which gas is absorbed?' } });
    expect((screen.getAllByTestId('vidya-surface-item-input')[0] as HTMLInputElement).value).toBe(
      'Which gas is absorbed?',
    );
  });

  it('never publishes from inside the surface — it only prepares + routes to review', () => {
    const onOpenHref = vi.fn();
    render(<VidyaSurface spec={quiz} onOpenHref={onOpenHref} />);

    // Pressing the consequential control does NOT execute — it surfaces the
    // approval note + the single review route.
    fireEvent.click(screen.getByTestId('vidya-surface-publish'));
    expect(screen.getByTestId('vidya-surface-approval')).toBeInTheDocument();
    expect(screen.getByTestId('vidya-surface-approval')).toHaveTextContent(/needs your approval/i);

    // Only following the review link routes the human (it never auto-fires).
    fireEvent.click(screen.getByTestId('vidya-surface-review'));
    expect(onOpenHref).toHaveBeenCalledWith('/teacher/assign');
  });

  it('keeps the answer key private — a learner-facing answer is never rendered', () => {
    render(<VidyaSurface spec={quiz} />);
    expect(screen.queryByText(/Carbon dioxide/)).toBeTruthy(); // an OPTION is fine to show
    // The teacher-only `answer` field is never surfaced as its own labelled value.
    expect(screen.queryByText(/answer key/i)).toBeNull();
  });
});

describe('VidyaSurface — class-view (read-only)', () => {
  const classView: ClassViewSurface = {
    kind: 'class-view',
    title: 'Class 9-B',
    section: '9-B',
    rows: [
      { label: 'Learner A', band: 'secure' },
      { label: 'Learner B', band: 'still building', needsAttention: true },
    ],
    summary: 'Most of the class is secure on fractions.',
  };
  it('renders rows with plain bands and an attention flag, no consequential control', () => {
    render(<VidyaSurface spec={classView} />);
    expect(screen.getByTestId('vidya-surface')).toHaveAttribute('data-surface-kind', 'class-view');
    expect(screen.getByText('Most of the class is secure on fractions.')).toBeInTheDocument();
    expect(screen.getByText('worth a look')).toBeInTheDocument();
    expect(screen.queryByTestId('vidya-surface-publish')).toBeNull();
  });
});

describe('VidyaSurface — plan-board (operable, adopt prepares)', () => {
  const plan: PlanBoardSurface = {
    kind: 'plan-board',
    title: 'A week on fractions',
    topic: 'fractions',
    columns: [
      { heading: 'Mon', cards: ['Recap halves'] },
      { heading: 'Tue', cards: ['Quarters'] },
    ],
    adopt: { label: 'Review and adopt', requiresApproval: true, openHref: '/teacher/plan' },
  };
  it('adopting only prepares + routes to the plan review page', () => {
    const onOpenHref = vi.fn();
    render(<VidyaSurface spec={plan} onOpenHref={onOpenHref} />);
    fireEvent.click(screen.getByTestId('vidya-surface-publish'));
    fireEvent.click(screen.getByTestId('vidya-surface-review'));
    expect(onOpenHref).toHaveBeenCalledWith('/teacher/plan');
  });
});

describe('VidyaSurface — report-card (read-only)', () => {
  const report: ReportCardSurface = {
    kind: 'report-card',
    title: 'How your child is doing',
    childLabel: 'your child',
    highlights: ['Strong on reading', 'Growing in number sense'],
    nextStep: 'A little practice on subtraction',
  };
  it('renders plain-language highlights and a next step', () => {
    render(<VidyaSurface spec={report} />);
    expect(screen.getByText('Strong on reading')).toBeInTheDocument();
    expect(screen.getByText(/A little practice on subtraction/)).toBeInTheDocument();
    expect(screen.queryByTestId('vidya-surface-publish')).toBeNull();
  });
});
