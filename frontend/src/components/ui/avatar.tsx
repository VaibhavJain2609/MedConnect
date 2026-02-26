import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const avatarVariants = cva(
  "relative inline-flex items-center justify-center overflow-hidden rounded-full bg-dreams-blue/10 text-dreams-blue font-medium select-none",
  {
    variants: {
      size: {
        sm: "h-8 w-8 text-xs",
        md: "h-12 w-12 text-sm",
        lg: "h-16 w-16 text-base",
        xl: "h-24 w-24 text-xl",
        "2xl": "h-32 w-32 text-2xl",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
);

const statusVariants = cva(
  "absolute bottom-0 right-0 rounded-full border-2 border-white",
  {
    variants: {
      size: {
        sm: "h-2 w-2",
        md: "h-3 w-3",
        lg: "h-4 w-4",
        xl: "h-5 w-5",
        "2xl": "h-6 w-6",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
);

export interface AvatarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
  src?: string | null;
  alt?: string;
  fallback?: string;
  showStatus?: boolean;
  statusColor?: "online" | "offline" | "busy" | "away";
}

/**
 * Avatar Component
 *
 * Displays a circular profile image with fallback to initials.
 *
 * Features:
 * - Multiple size variants (sm, md, lg, xl, 2xl)
 * - Fallback to initials if no image provided
 * - Optional status indicator (online/offline/busy/away)
 * - Colored border support
 *
 * @example
 * <Avatar size="md" src="/path/to/image.jpg" alt="John Doe" fallback="JD" />
 * <Avatar size="lg" fallback="AB" showStatus statusColor="online" />
 */
export const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  (
    {
      src,
      alt,
      fallback,
      size,
      showStatus,
      statusColor = "online",
      className,
      ...props
    },
    ref
  ) => {
    const [imageError, setImageError] = React.useState(false);

    const statusColors = {
      online: "bg-status-completed",
      offline: "bg-gray-400",
      busy: "bg-status-overdue",
      away: "bg-status-pending",
    };

    const getInitials = (text?: string) => {
      if (!text) return "?";
      const words = text.trim().split(" ");
      if (words.length >= 2) {
        return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
      }
      return text.substring(0, 2).toUpperCase();
    };

    const displayFallback = fallback || getInitials(alt);

    return (
      <div
        ref={ref}
        className={cn(avatarVariants({ size }), className)}
        {...props}
      >
        {src && !imageError ? (
          <img
            src={src}
            alt={alt || "Avatar"}
            className="h-full w-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <span>{displayFallback}</span>
        )}
        {showStatus && (
          <span
            className={cn(
              statusVariants({ size }),
              statusColors[statusColor]
            )}
            aria-label={`Status: ${statusColor}`}
          />
        )}
      </div>
    );
  }
);

Avatar.displayName = "Avatar";

/**
 * AvatarGroup Component
 *
 * Displays multiple avatars in a stacked group
 *
 * @example
 * <AvatarGroup max={3}>
 *   <Avatar src="/user1.jpg" fallback="JD" />
 *   <Avatar src="/user2.jpg" fallback="SM" />
 *   <Avatar src="/user3.jpg" fallback="AB" />
 * </AvatarGroup>
 */
export interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  max?: number;
  size?: AvatarProps["size"];
  children: React.ReactNode;
}

export const AvatarGroup: React.FC<AvatarGroupProps> = ({
  max = 3,
  size = "md",
  children,
  className,
  ...props
}) => {
  const childArray = React.Children.toArray(children);
  const displayChildren = max ? childArray.slice(0, max) : childArray;
  const remaining = childArray.length - displayChildren.length;

  return (
    <div className={cn("flex -space-x-2", className)} {...props}>
      {displayChildren.map((child, index) => (
        <div key={index} className="ring-2 ring-white rounded-full">
          {React.isValidElement<AvatarProps>(child)
            ? React.cloneElement(child, { size })
            : child}
        </div>
      ))}
      {remaining > 0 && (
        <div className={cn(avatarVariants({ size }), "ring-2 ring-white")}>
          <span>+{remaining}</span>
        </div>
      )}
    </div>
  );
};

AvatarGroup.displayName = "AvatarGroup";
