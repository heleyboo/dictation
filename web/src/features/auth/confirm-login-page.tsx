import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api/client";
import { safeReturnTo } from "./safe-return-to";
import { ME_KEY } from "./use-me";

/**
 * Magic-link landing page. The emailed link opens this page; only the button press consumes the
 * single-use token, so email security scanners that pre-fetch links cannot use it up.
 */
export function ConfirmLoginPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const qc = useQueryClient();

  const preview = useQuery({
    queryKey: ["magic-link", token],
    enabled: Boolean(token),
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/auth/magic-link/preview", { params: { query: { token } } });
      if (error || !data) throw new Error(errorMessage(error, "Liên kết đã hết hạn hoặc đã được dùng."));
      return data;
    },
  });

  const confirm = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/auth/magic-link/verify", { body: { token } });
      if (error || !data) throw new Error(errorMessage(error, "Liên kết đã hết hạn hoặc đã được dùng."));
      return data;
    },
    onSuccess: async ({ return_to }) => {
      await qc.invalidateQueries({ queryKey: ME_KEY });
      navigate(safeReturnTo(return_to), { replace: true });
    },
  });

  const failure = !token ? "Thiếu mã đăng nhập." : (preview.error ?? confirm.error)?.message;

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-5 px-4">
      <h1 className="font-serif text-3xl text-ink">Đăng nhập</h1>
      {failure ? (
        <>
          <p role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
            {failure}
          </p>
          <Button variant="outline" asChild>
            <Link to="/login">Gửi liên kết mới</Link>
          </Button>
        </>
      ) : preview.isPending ? (
        <p className="text-sm text-ink-3">Đang kiểm tra liên kết…</p>
      ) : (
        <>
          <p className="text-ink-2">
            Đăng nhập với tài khoản <strong className="text-ink">{preview.data?.email}</strong>?
          </p>
          <Button size="lg" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
            Đăng nhập
          </Button>
          <p className="text-xs text-ink-3">Không phải email của bạn? Đóng trang này.</p>
        </>
      )}
    </main>
  );
}
