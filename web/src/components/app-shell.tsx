import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { ME_KEY, useMe } from "@/features/auth/use-me";
import { api, setCsrfToken } from "@/lib/api/client";

export function AppShell() {
  const me = useMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSettled: () => {
      setCsrfToken(null);
      qc.clear();
      qc.setQueryData(ME_KEY, null);
      navigate("/");
    },
  });

  return (
    <div className="min-h-dvh bg-bg">
      <header className="border-b border-line bg-surface">
        <nav className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6" aria-label="Chính">
          <Link to="/" className="font-serif text-xl text-ink">
            Dictation
          </Link>
          {me.data?.role === "admin" && (
            <Link to="/admin" className="text-sm text-ink-2 hover:text-ink">
              Quản trị
            </Link>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm">
            {me.data ? (
              <>
                <span className="text-ink-2">{me.data.name || me.data.email}</span>
                <Button size="sm" variant="ghost" disabled={logout.isPending} onClick={() => logout.mutate()}>
                  Đăng xuất
                </Button>
              </>
            ) : (
              !me.isPending && (
                <Button size="sm" variant="outline" asChild>
                  <Link to="/login">Đăng nhập</Link>
                </Button>
              )
            )}
          </div>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
