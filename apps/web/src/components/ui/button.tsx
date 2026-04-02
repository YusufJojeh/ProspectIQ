import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(15,118,110,0.18)] disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary:
          "bg-[color:var(--accent)] text-white shadow-[0_18px_40px_-24px_rgba(15,118,110,0.9)] hover:brightness-105",
        secondary:
          "border border-[color:var(--border)] bg-white text-[color:var(--text)] hover:bg-[color:var(--surface-soft)]",
        ghost: "text-[color:var(--muted)] hover:bg-white/70 hover:text-[color:var(--text)]",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ asChild = false, className, type = "button", variant, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant }), className)}
      {...(!asChild ? { type } : {})}
      {...props}
    />
  );
}

export { buttonVariants };
