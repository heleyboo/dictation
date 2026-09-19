import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api/client";
import { useMe } from "./use-me";

const ERRORS: Record<string, string> = {
  google: "Đăng nhập Google không thành công. Vui lòng thử lại.",
  link_expired: "Liên kết đăng nhập đã hết hạn hoặc đã được dùng. Hãy gửi liên kết mới.",
};
const RESEND_AFTER_SECONDS = 60;

/** Only same-site paths may be used as a post-login destination (the API enforces this too). */
function safeReturnTo(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export function LoginPage() {
  const [params] = useSearchParams();
  const returnTo = safeReturnTo(params.get("return_to"));
  const error = params.get("error");
  const me = useMe();
  const config = useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => (await api.GET("/api/v1/auth/config")).data ?? null,
  });

  if (me.data) return <Navigate to={returnTo} replace />;

  const googleHref = `/api/v1/auth/google/start?return_to=${encodeURIComponent(returnTo)}`;

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4">
      <div>
        <h1 className="font-serif text-3xl text-ink">Đăng nhập</h1>
        <p className="mt-1 text-sm text-ink-2">Lưu tiến độ học và sổ tay từ vựng của bạn.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
          {ERRORS[error] ?? "Đăng nhập không thành công."}
        </p>
      )}
      {config.data?.google_enabled !== false && (
        <Button asChild size="lg">
          <a href={googleHref}>Đăng nhập với Google</a>
        </Button>
      )}
      {config.data?.magic_link_enabled && (
        <MagicLinkForm returnTo={returnTo} showDivider={config.data.google_enabled} />
      )}
    </main>
  );
}

function MagicLinkForm({ returnTo, showDivider }: { returnTo: string; showDivider: boolean }) {
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const send = useMutation({
    mutationFn: async (address: string) => {
      const { error } = await api.POST("/api/v1/auth/magic-link", { body: { email: address, return_to: returnTo } });
      if (error) throw new Error(errorMessage(error));
    },
    onSuccess: (_, address) => {
      setSentTo(address);
      setCooldown(RESEND_AFTER_SECONDS);
    },
  });

  if (sentTo) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 text-sm" role="status">
        <p className="font-medium text-ink">✉ Kiểm tra email của bạn</p>
        <p className="text-ink-2">
          Chúng tôi đã gửi liên kết đăng nhập tới <strong className="text-ink">{sentTo}</strong>. Liên kết hết hạn sau
          15 phút.
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={cooldown > 0 || send.isPending}
            onClick={() => send.mutate(sentTo)}
          >
            {cooldown > 0 ? `Gửi lại sau 0:${String(cooldown).padStart(2, "0")}` : "Gửi lại"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSentTo(null)}>
            Đổi email
          </Button>
        </div>
      </div>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send.mutate(email.trim());
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      {showDivider && (
        <div className="flex items-center gap-3 text-xs text-ink-3">
          <span className="h-px flex-1 bg-line" />
          hoặc
          <span className="h-px flex-1 bg-line" />
        </div>
      )}
      <Label htmlFor="email">Email</Label>
      <Input
        id="email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      {send.isError && <p className="text-sm text-bad">{send.error.message}</p>}
      <Button type="submit" variant="outline" disabled={send.isPending}>
        Gửi liên kết đăng nhập
      </Button>
    </form>
  );
}
