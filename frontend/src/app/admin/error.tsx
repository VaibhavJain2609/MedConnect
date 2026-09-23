"use client";

import { useTranslations } from "next-intl";
import { RouteError } from "@/components/shared/route-boundaries";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("common");
  return (
    <RouteError
      error={error}
      reset={reset}
      homeHref="/admin/dashboard"
      homeLabel={t("goToDashboard")}
    />
  );
}
