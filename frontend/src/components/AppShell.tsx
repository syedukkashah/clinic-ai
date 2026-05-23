import AdminLayout from "@/components/Admin/AdminLayout.jsx";

export function AppShell({ children }: { children: React.ReactNode }) {
  return <AdminLayout routeContent={children} />;
}
