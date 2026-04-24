import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

export type BadgeTone =
  | 'accent'
  | 'signal'
  | 'evidence'
  | 'caution'
  | 'warning'
  | 'risk'
  | 'muted'
  | 'neutral'
  | 'danger'
  | 'success'
  | 'loading'
  | 'info'
  | 'error'

const TONE_CLASSES: Record<BadgeTone, string> = {
  accent:
    'border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.1)] text-[oklch(var(--signal))]',
  signal:
    'border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.1)] text-[oklch(var(--signal))]',
  evidence:
    'border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.1)] text-[oklch(var(--evidence))]',
  caution:
    'border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.1)] text-[oklch(var(--caution))]',
  warning:
    'border-[oklch(var(--caution)/0.3)] bg-[oklch(var(--caution)/0.1)] text-[oklch(var(--caution))]',
  risk: 'border-[oklch(var(--risk)/0.3)] bg-[oklch(var(--risk)/0.1)] text-[oklch(var(--risk))]',
  muted: 'border-border bg-muted/30 text-muted-foreground',
  neutral: 'border-border bg-muted/30 text-muted-foreground',
  danger: 'border-destructive/30 bg-destructive/10 text-destructive',
  success:
    'border-[oklch(var(--evidence)/0.3)] bg-[oklch(var(--evidence)/0.1)] text-[oklch(var(--evidence))]',
  loading: 'border-border bg-muted/30 text-muted-foreground',
  info: 'border-border bg-muted/30 text-muted-foreground',
  error: 'border-destructive/30 bg-destructive/10 text-destructive',
}

const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive transition-[color,box-shadow] overflow-hidden',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground [a&]:hover:bg-primary/90',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground [a&]:hover:bg-secondary/90',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground [a&]:hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60',
        outline:
          'text-foreground [a&]:hover:bg-accent [a&]:hover:text-accent-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

function Badge({
  className,
  variant,
  tone,
  asChild = false,
  ...props
}: React.ComponentProps<'span'> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean; tone?: BadgeTone }) {
  const Comp = asChild ? Slot : 'span'

  return (
    <Comp
      data-slot="badge"
      className={cn(tone ? TONE_CLASSES[tone] : badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
