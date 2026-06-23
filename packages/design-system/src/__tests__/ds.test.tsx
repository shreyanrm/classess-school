import { describe, it, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { cx } from '../components/cx';
import { SpotlightCard } from '../components/SpotlightCard';
import { Tag } from '../components/Tag';

describe('cx', () => {
  it('joins truthy class names and drops falsy ones', () => {
    expect(cx('a', false, undefined, 'b', null, 'c')).toBe('a b c');
  });
});

describe('SpotlightCard — the signature hover', () => {
  it('renders a .card with the .c-spot contract class', () => {
    const { container } = render(
      <SpotlightCard>
        <p>Move your pointer</p>
      </SpotlightCard>,
    );
    const el = container.firstElementChild as HTMLElement;
    expect(el).toBeInTheDocument();
    expect(el.classList.contains('card')).toBe(true);
    expect(el.classList.contains('c-spot')).toBe(true);
    expect(screen.getByText('Move your pointer')).toBeInTheDocument();
  });
});

describe('Tag', () => {
  it('renders its children', () => {
    render(<Tag>Mastered</Tag>);
    expect(screen.getByText('Mastered')).toBeInTheDocument();
  });
});
