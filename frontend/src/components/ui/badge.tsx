import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-dreams-blue text-white hover:bg-dreams-blue/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        // Dreams EMR Status Variants — WCAG AA pairs (>= 4.5:1) matching
        // StatusBadge's TONE_CLASSES; the status-* 500-level hues only reach
        // 2.1–4.2:1 on their /10 tints and fail AA for small text.
        inProgress:
          "border-purple-200 bg-purple-100 text-purple-800 hover:bg-purple-200",
        completed:
          "border-green-200 bg-green-100 text-green-800 hover:bg-green-200",
        pending:
          "border-amber-200 bg-amber-100 text-amber-800 hover:bg-amber-200",
        overdue:
          "border-red-200 bg-red-100 text-red-800 hover:bg-red-200",
        upcoming:
          "border-blue-200 bg-blue-100 text-blue-800 hover:bg-blue-200",
        cancelled:
          "border-gray-200 bg-gray-100 text-gray-700 hover:bg-gray-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
