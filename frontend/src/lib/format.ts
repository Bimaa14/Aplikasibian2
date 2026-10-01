// Format helpers — IDR (Rupiah) with Indonesian thousand separators, Indonesian dates.
import { ApiError } from "./api";

const idrFormatter = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 2,
});
const compactFormatter = new Intl.NumberFormat("id-ID", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatIDR(value: number | null | undefined): string {
  return idrFormatter.format(value ?? 0);
}

export function formatIDRCompact(value: number | null | undefined): string {
  return `Rp ${compactFormatter.format(value ?? 0)}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleDateString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })} ${date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Tanggal hari ini menurut browser — display-only (default input tanggal & badge); keputusan
 * bisnis tetap divalidasi server via lib/dates.py. Format YYYY-MM-DD. */
export function todayLocalISO(): string {
  return new Date().toLocaleDateString("sv-SE");
}

/** Selisih hari menuju tanggal due (positif = masih ada waktu, negatif = lewat). */
export function daysUntil(dateStr: string): number {
  const [y, m, d] = dateStr.slice(0, 10).split("-").map(Number); // toleransi ISO dengan waktu (…T00:00:00)
  if (!y || !m || !d || Number.isNaN(y + m + d)) return 0;
  const due = new Date(y, m - 1, d).getTime();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((due - today) / 86_400_000);
}

/** Pesan error ramah dari ApiError (termasuk 422 FastAPI {detail: [...]}) */
export function getApiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg.replace(/^Value error,\s*/i, "");
    }
    if (error.status === 401) return "Username atau password salah";
    if (error.status === 404) return "Data tidak ditemukan";
    if (error.status === 422) return "Data yang dikirim tidak valid";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Terjadi kesalahan. Coba lagi.";
}
