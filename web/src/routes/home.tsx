import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

/** Placeholder home page: proves web → Caddy/Vite proxy → API → Postgres works end to end. */
export function HomePage() {
  const health = useQuery({
    queryKey: ["healthz"],
    queryFn: async () => {
      // 503 still carries a Health body ("degraded"), so show it instead of a generic error.
      const { data, error, response } = await api.GET("/api/v1/healthz");
      const body = data ?? error;
      if (!body) throw new Error(`HTTP ${response.status}`);
      return body;
    },
    retry: false,
  });

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 px-4 py-16">
      <h1 className="font-serif text-4xl text-ink">Dictation</h1>
      <p className="text-ink-2">Luyện nghe tiếng Anh bằng chép chính tả.</p>
      <p role="status" className="font-mono text-sm">
        {health.isPending && <span className="text-ink-3">Đang kiểm tra API…</span>}
        {health.isError && <span className="text-bad">API lỗi: {health.error.message}</span>}
        {health.data &&
          (health.data.status === "ok" ? (
            <span className="text-ok">API OK · DB {health.data.db}</span>
          ) : (
            <span className="text-warn">
              API {health.data.status} · DB {health.data.db}
            </span>
          ))}
      </p>
    </main>
  );
}
