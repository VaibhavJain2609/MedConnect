import * as React from "react";
import { Inbox, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface EmptyStateProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Icon shown above the title. Pass a Lucide icon component
   * (e.g. `icon={FileText}`) or a rendered node. Defaults to `Inbox`.
   */
  icon?: LucideIcon | React.ReactNode;
  /** Short headline describing the empty state. */
  title: string;
  /** Optional supporting text explaining why it's empty or what to do next. */
  description?: string;
  /** Optional call-to-action rendered below the description (button, link…). */
  action?: React.ReactNode;
}

/**
 * EmptyState
 *
 * Standard "nothing here yet" block: icon + title + optional description +
 * optional action. Replaces the hand-rolled empty states scattered across
 * the portals.
 *
 * @example
 * <EmptyState
 *   icon={Pill}
 *   title="No prescriptions found"
 *   description="Prescriptions you issue will appear here."
 *   action={<Button onClick={...}>New prescription</Button>}
 * />
 */
function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  ...props
}: EmptyStateProps) {
  const iconNode =
    icon == null ? (
      <Inbox className="h-6 w-6 text-dreams-textSecondary" />
    ) : typeof icon === "function" ? (
      React.createElement(icon, {
        className: "h-6 w-6 text-dreams-textSecondary",
        "aria-hidden": true,
      })
    ) : (
      icon
    );

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 py-12 text-center",
        className
      )}
      {...props}
    >
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-dreams-lightBg">
        {iconNode}
      </div>
      <p className="text-sm font-semibold text-dreams-textPrimary">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-dreams-textSecondary">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export { EmptyState };
