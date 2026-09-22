import { AuthGuard } from "@/components/layout/auth-guard";
import { PatientLayout } from "@/components/layout/patient-layout";
import { InstallPrompt } from "@/components/pwa/InstallPrompt";

export default function PatientRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard requiredRole="patient">
      <PatientLayout>{children}</PatientLayout>
      <InstallPrompt />
    </AuthGuard>
  );
}
