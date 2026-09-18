import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useMe } from "./use-me";

function Pending() {
  return <p className="p-8 text-sm text-ink-3">Đang tải…</p>;
}

/** Signed-in users only; others go to /login and come back afterwards (AC-M1-04.1). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Pending />;
  if (!me.data) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?return_to=${returnTo}`} replace />;
  }
  return children;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <Pending />;
  if (me.data?.role !== "admin") {
    return (
      <main className="mx-auto max-w-xl px-4 py-16">
        <h1 className="font-serif text-2xl text-ink">Không có quyền truy cập</h1>
        <p className="mt-2 text-ink-2">Trang này chỉ dành cho quản trị viên.</p>
      </main>
    );
  }
  return children;
}
