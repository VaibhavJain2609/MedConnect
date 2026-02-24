import { AuthGuard } from "@/components/layout/auth-guard";
import { AdminLayout } from "@/components/admin/admin-layout";

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard requiredRole="admin">
      <AdminLayout>{children}</AdminLayout>
    </AuthGuard>
  );
}
