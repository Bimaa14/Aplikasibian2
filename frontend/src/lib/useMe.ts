// Sesi: siapa yang login dijawab oleh GET /api/auth/me (httpOnly cookie). retry: false —
// 401 harus langsung terlihat tanpa 3x percobaan ulang.
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./api";
import type { User } from "./types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<User>("/auth/me"),
    retry: false,
  });
}
