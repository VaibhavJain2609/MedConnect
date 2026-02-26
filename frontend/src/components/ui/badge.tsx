import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        // Dreams EMR Status Variants
        inProgress:
          "border-transparent bg-status-inProgress/10 text-status-inProgress hover:bg-status-inProgress/20",
        completed:
          "border-transparent bg-status-completed/10 text-status-completed hover:bg-status-completed/20",
        pending:
          "border-transparent bg-status-pending/10 text-status-pending hover:bg-status-pending/20",
        overdue:
          "border-transparent bg-status-overdue/10 text-status-overdue hover:bg-status-overdue/20",
        upcoming:
          "border-transparent bg-status-upcoming/10 text-status-upcoming hover:bg-status-upcoming/20",
        cancelled:
          "border-transparent bg-gray-100 text-gray-600 hover:bg-gray-200",
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
