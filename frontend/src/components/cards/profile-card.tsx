"use client";

import * as React from "react";
import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ProfileCardProps {
  id: string;
  name: string;
  photo?: string | null;
  status: "inProgress" | "completed" | "pending" | "overdue" | "upcoming";
  statusLabel?: string;
  infoItems: Array<{
    label: string;
    value: string;
  }>;
  href?: string;
  ctaLabel?: string;
  onCtaClick?: () => void;
  className?: string;
}

/**
 * ProfileCard Component
 *
 * Displays a patient or doctor profile card with large avatar, status badge, and info grid
 *
 * Features:
 * - Large circular profile photo (Avatar component)
 * - ID badge with link
 * - Status badge at top
 * - 3-column info grid (Last Visit, Gender, Location, etc.)
 * - Optional CTA button at bottom
 *
 * @example
 * <ProfileCard
 *   id="P-001"
 *   name="John Doe"
 *   photo="/path/to/photo.jpg"
 *   status="completed"
 *   statusLabel="In Patient"
 *   infoItems={[
 *     { label: "Last Visit", value: "2 days ago" },
 *     { label: "Gender", value: "Male" },
 *     { label: "Location", value: "New York" }
 *   ]}
 *   href="/patients/p-001"
 *   ctaLabel="View Profile"
 * />
 */
export const ProfileCard: React.FC<ProfileCardProps> = ({
  id,
  name,
  photo,
  status,
  statusLabel,
  infoItems,
  href,
  ctaLabel = "View Details",
  onCtaClick,
  className,
}) => {
  return (
    <div
      className={cn(
        "bg-white rounded-lg shadow-card hover:shadow-card-hover transition-shadow p-6",
        className
      )}
    >
      {/* Status Badge */}
      <div className="flex justify-end mb-3">
        <Badge variant={status}>
          {statusLabel || status.charAt(0).toUpperCase() + status.slice(1)}
        </Badge>
      </div>

      {/* Avatar */}
      <div className="flex justify-center mb-4">
        <Avatar
          src={photo}
          alt={name}
          fallback={name}
          size="2xl"
          className="shadow-md"
        />
      </div>

      {/* ID Badge */}
      {href ? (
        <Link
          href={href}
          className="block text-center mb-2 text-sm font-medium text-dreams-blue hover:underline"
        >
          {id}
        </Link>
      ) : (
        <p className="text-center mb-2 text-sm font-medium text-dreams-blue">
          {id}
        </p>
      )}

      {/* Name */}
      <h3 className="text-center text-lg font-bold text-dreams-textPrimary mb-4">
        {name}
      </h3>

      {/* Info Grid */}
      <div className="grid grid-cols-3 gap-3 mb-4 border-t border-dreams-border pt-4">
        {infoItems.slice(0, 3).map((item, index) => (
          <div key={index} className="text-center">
            <p className="text-xs text-dreams-textSecondary mb-1">
              {item.label}
            </p>
            <p className="text-sm font-medium text-dreams-textPrimary truncate">
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* CTA Button */}
      {(href || onCtaClick) && (
        <div className="mt-4">
          {href ? (
            <Link
              href={href}
              className="block w-full py-2 px-4 bg-dreams-blue text-white text-center text-sm font-medium rounded-md hover:opacity-90 transition-opacity"
            >
              {ctaLabel}
            </Link>
          ) : (
            <button
              onClick={onCtaClick}
              className="w-full py-2 px-4 bg-dreams-blue text-white text-sm font-medium rounded-md hover:opacity-90 transition-opacity"
            >
              {ctaLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

ProfileCard.displayName = "ProfileCard";
