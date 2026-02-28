import { AuthGuard } from "@/components/layout/auth-guard";
import { DoctorLayout } from "@/components/layout/doctor-layout";

export default function DoctorRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard requiredRole="doctor">
      <DoctorLayout>{children}</DoctorLayout>
    </AuthGuard>
  );
}
