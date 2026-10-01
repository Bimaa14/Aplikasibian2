// Blok status generik untuk area data (loading / kosong / error) — halaman tetap render
// shell-nya meski fetch gagal (aturan static preview: never gate a page on a fetch).
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/lib/format";
import { cn } from "@/lib/utils";

export function LoadingBlock({ label = "Memuat data…", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("space-y-3 rounded-lg border border-border bg-card p-5", className)} data-testid="loading-block">
      <div className="h-4 w-1/3 animate-pulse rounded bg-secondary" />
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded bg-secondary"
          style={{ width: `${90 - i * 15}%`, animationDelay: `${i * 120}ms` }}
        />
      ))}
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

export function EmptyBlock({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-card/50 p-8 text-center", className)}
      data-testid="empty-block"
    >
      <p className="font-heading font-semibold">{title}</p>
      {description ? <p className="max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {action}
    </div>
  );
}

export function ErrorBlock({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center", className)}
      data-testid="error-block"
    >
      <p className="font-heading font-semibold text-red-700 dark:text-red-400">Gagal memuat data</p>
      <p className="max-w-sm text-sm text-muted-foreground">{getApiErrorMessage(error)}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry} data-testid="error-retry-button">
          Coba Lagi
        </Button>
      ) : null}
    </div>
  );
}
