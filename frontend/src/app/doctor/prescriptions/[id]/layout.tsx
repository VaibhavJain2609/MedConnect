/**
 * Layout for individual prescription routes.
 * The /print sub-route needs minimal layout (no sidebar).
 * The parent doctor layout wraps everything, but print overrides styles via CSS.
 */

export default function PrescriptionIdLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
