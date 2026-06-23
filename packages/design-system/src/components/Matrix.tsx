import { forwardRef, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export interface MatrixProps extends HTMLAttributes<HTMLDivElement> {
  /** Number of columns. Sets grid-template-columns to repeat(columns, 1fr). */
  columns?: number;
  children?: ReactNode;
}

/**
 * The tight matrix — cells stacked close, sharing hairlines (no gaps). The
 * grid gap reveals the border colour as 1px rules between cells. Sharp,
 * structural, no shadow.
 */
export const Matrix = forwardRef<HTMLDivElement, MatrixProps>(function Matrix(
  { columns, className, style, children, ...rest },
  ref,
) {
  const gridStyle: CSSProperties | undefined = columns
    ? { gridTemplateColumns: `repeat(${columns}, 1fr)`, ...style }
    : style;
  return (
    <div ref={ref} className={cx('matrix', className)} style={gridStyle} {...rest}>
      {children}
    </div>
  );
});

export interface CellProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

/**
 * A matrix cell. On hover the surface raises and the ultramarine signature
 * line wipes across the top — the shared-hairline equivalent of a lift, with
 * no drop shadow.
 */
export const Cell = forwardRef<HTMLDivElement, CellProps>(function Cell(
  { className, children, ...rest },
  ref,
) {
  return (
    <div ref={ref} className={cx('cell', className)} {...rest}>
      {children}
    </div>
  );
});
