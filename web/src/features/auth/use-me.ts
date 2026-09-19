import { useQuery } from "@tanstack/react-query";
import { api, setCsrfToken, type Schemas } from "@/lib/api/client";

export type Me = Schemas["Me"];

export const ME_KEY = ["me"] as const;

/** Current user, or null when signed out (401). Also primes the CSRF token for later writes. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      const { data, response } = await api.GET("/api/v1/me");
      if (response.status === 401) {
        setCsrfToken(null);
        return null;
      }
      if (!data) throw new Error(`HTTP ${response.status}`);
      setCsrfToken(data.csrf_token);
      return data;
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}
