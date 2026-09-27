// Badge status dengan indikator titik (6px radius, bold tracking) — menandai selesai/retur,
// lunas/belum dibayar, dan peringatan jatuh tempo (merah berdenyut = lewat tempo).
import { cn } from "@/lib/utils";
import { daysUntil } from "@/lib/format";
import type { DebtStatus, TxStatus } from "@/lib/types";

const BASE =
  "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider";
const DOT = "size-1.5 rounded-full bg-current";

export function TxStatusBadge({ status }: { status: TxStatus }) {
  const completed = status === "completed";
  return (
    <span
      data-testid="tx-status-badge"
      className={cn(
        BASE,
        completed
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
          : "border-red-500/30 bg-red-500/10 text-red-400"
      )}
    >
      <span className={DOT} />
      {completed ? "Selesai" : "Retur"}
    </span>
  );
}

export function DebtStatusBadge({ status, dueDate }: { status: DebtStatus; dueDate?: string | null }) {
  if (status === "paid") {
    return (
      <span data-testid="debt-status-badge" className={cn(BASE, "border-emerald-500/30 bg-emerald-500/10 text-emerald-400")}>
        <span className={DOT} />
        Lunas
      </span>
    );
  }
  const days = dueDate ? daysUntil(dueDate) : null;
  if (days !== null && days < 0) {
    return (
      <span data-testid="debt-status-badge" className={cn(BASE, "overdue-pulse border-red-500/40 bg-red-500/15 text-red-400")}>
        <span className={DOT} />
        Lewat Jatuh Tempo
      </span>
    );
  }
  if (days !== null && days <= 3) {
    return (
      <span data-testid="debt-status-badge" className={cn(BASE, "border-amber-500/40 bg-amber-500/15 text-amber-300")}>
        <span className={DOT} />
        {days === 0 ? "Jatuh Tempo Hari Ini" : `Jatuh Tempo H-${days}`}
      </span>
    );
  }
  return (
    <span data-testid="debt-status-badge" className={cn(BASE, "border-amber-500/25 bg-amber-500/10 text-amber-300/90")}>
      <span className={DOT} />
      Belum Dibayar
    </span>
  );
}

export function PaymentMethodBadge({ method }: { method: "cash" | "credit" }) {
  const cash = method === "cash";
  return (
    <span
      data-testid="payment-method-badge"
      className={cn(
        BASE,
        cash
          ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
          : "border-orange-500/30 bg-orange-500/10 text-orange-400"
      )}
    >
      {cash ? "Tunai" : "Tempo"}
    </span>
  );
}
