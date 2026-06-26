import { forwardRef } from 'react';
import {
  Home,
  LayoutGrid,
  Search,
  Sparkles,
  Flame,
  Target,
  BookOpen,
  LineChart,
  Send,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Info,
  TriangleAlert,
  CircleAlert,
  CircleCheck,
  Bell,
  Settings,
  User,
  Calendar,
  Clock,
  ArrowRight,
  ArrowUpRight,
  Plus,
  Minus,
  FileText,
  Upload,
  Trash2,
  MapPin,
  type LucideIcon,
  type LucideProps,
} from 'lucide-react';

/**
 * House icon set. Lucide-backed, mapped to brand-friendly names. The 1.5px
 * stroke, currentColor, round caps/joins are the house style (matches the
 * .icon class in components.css). Add to this map as surfaces need glyphs;
 * never reach past it to a raw <svg> with a hardcoded stroke.
 */
const REGISTRY = {
  home: Home,
  grid: LayoutGrid,
  search: Search,
  spark: Sparkles,
  flame: Flame,
  target: Target,
  book: BookOpen,
  chart: LineChart,
  send: Send,
  check: Check,
  close: X,
  'chevron-down': ChevronDown,
  'chevron-right': ChevronRight,
  info: Info,
  warning: TriangleAlert,
  danger: CircleAlert,
  success: CircleCheck,
  bell: Bell,
  settings: Settings,
  user: User,
  calendar: Calendar,
  clock: Clock,
  'arrow-right': ArrowRight,
  'arrow-up-right': ArrowUpRight,
  plus: Plus,
  minus: Minus,
  file: FileText,
  upload: Upload,
  trash: Trash2,
  pin: MapPin,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof REGISTRY;

/** All available house icon names, for pickers and docs. */
export const iconNames = Object.keys(REGISTRY) as IconName[];

export interface IconProps extends Omit<LucideProps, 'ref'> {
  /** A house icon name. */
  name: IconName;
  /** Convenience sizing matching the CSS scale. Default 'md' (20px). */
  size?: 'sm' | 'md' | 'lg';
}

const PX = { sm: 16, md: 20, lg: 24 } as const;

/**
 * Render a house icon at the brand stroke weight. Pass `name` and optionally
 * `size`. Inherits color from currentColor so it tints with its container.
 */
export const Icon = forwardRef<SVGSVGElement, IconProps>(function Icon(
  { name, size = 'md', className, ...rest },
  ref,
) {
  const Glyph = REGISTRY[name];
  return (
    <Glyph
      ref={ref}
      width={PX[size]}
      height={PX[size]}
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={['icon', size === 'sm' ? 'icon-sm' : size === 'lg' ? 'icon-lg' : '', className]
        .filter(Boolean)
        .join(' ')}
      aria-hidden={rest['aria-label'] ? undefined : true}
      {...rest}
    />
  );
});
