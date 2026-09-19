/**
 * Post-login destination: only a path on this site. Parsing against the current origin catches
 * tricks like `//evil.com` or `/\evil.com` that browsers treat as another host.
 */
export function safeReturnTo(value: string | null, origin = window.location.origin): string {
  if (!value || !value.startsWith("/")) return "/";
  try {
    const url = new URL(value, origin);
    return url.origin === origin ? url.pathname + url.search + url.hash : "/";
  } catch {
    return "/";
  }
}
