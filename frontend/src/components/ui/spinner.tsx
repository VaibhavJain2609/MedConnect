import * as React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const spinnerSizes = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
} as const;

export interface SpinnerProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** Visual size of the spinner icon. Defaults to "md". */
  size?: keyof typeof spinnerSizes;
  /** Accessible label announced to screen readers. Defaults to "Loading". */
  label?: string;
}

/**
 * Spinner
 *
 * Accessible loading indicator. Wraps the icon in `role="status"` with an
 * sr-only label so screen readers announce the busy state.
 *
 * @example
 * <Spinner />
 * <Spinner size="sm" label="Uploading photo" />
 * <Spinner size="lg" className="mx-auto" />
 */
function Spinner({
  size = "md",
  label = "Loading",
  className,
  ...props
}: SpinnerProps) {
  return (
    <span
      role="status"
      className={cn("inline-flex items-center", className)}
      {...props}
    >
      <Loader2
        aria-hidden="true"
        className={cn("animate-spin text-dreams-blue", spinnerSizes[size])}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export { Spinner };
