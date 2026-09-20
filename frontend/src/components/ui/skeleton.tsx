import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Skeleton
 *
 * Placeholder block shown while content is loading. Compose with Tailwind
 * sizing classes to mirror the layout that will replace it.
 *
 * @example
 * <Skeleton className="h-8 w-48" />
 * <Skeleton className="h-24 w-full rounded-xl" />
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-gray-200", className)}
      {...props}
    />
  );
}

export interface SkeletonTextProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /** Number of text lines to render. Defaults to 3. */
  lines?: number;
}

/**
 * SkeletonText
 *
 * A stack of skeleton bars that mimics a paragraph. The last line is
 * shortened, matching how real wrapped text usually ends.
 */
function SkeletonText({ lines = 3, className, ...props }: SkeletonTextProps) {
  return (
    <div className={cn("space-y-2", className)} {...props}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

export { Skeleton, SkeletonText };
