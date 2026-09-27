import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Car, Droplet, Search, CircleDot } from "lucide-react";
import { PaymentMethodBadge, TxStatusBadge } from "@/components/StatusBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import { formatDate, formatDateTime, formatIDR } from "@/lib/format";
import type { VehicleDetail, VehicleServiceSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function VehiclesPage() {
  const [search, setSearch] = useState("");
  const [plate, setPlate] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["vehicles", search.trim().toUpperCase()],
    queryFn: () =>
      apiGet<VehicleServiceSummary[]>(
        `/vehicles${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`
      ),
  });
  const detailQuery = useQuery({
    queryKey: ["vehicle", plate],
    queryFn: () => apiGet<VehicleDetail>(`/vehicles/${encodeURIComponent(plate ?? "")}`),
    enabled: !!plate,
  });

  const vehicles = listQuery.data ?? [];
  const detail = detailQuery.data;

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4">
        <h1 className="font-heading text-2xl font-bold tracking-tight">Riwayat Kendaraan</h1>
        <p className="text-sm text-muted-foreground">
          Cari nomor polisi untuk melihat semua servis kendaraan itu — termasuk ban dan oli terakhir yang dipakai.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {/* Daftar kendaraan */}
        <div className="xl:col-span-5">
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="vehicle-search-input"
              className="pl-9 font-mono uppercase"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nomor polisi… mis. B 1234 XYZ"
            />
          </div>

          {listQuery.isPending ? (
            <LoadingBlock />
          ) : listQuery.isError ? (
            <ErrorBlock error={listQuery.error} onRetry={() => void listQuery.refetch()} />
          ) : vehicles.length === 0 ? (
            <EmptyBlock
              title="Belum ada riwayat kendaraan"
              description="Isi nomor polisi saat checkout di Kasir POS agar servis tercatat per kendaraan."
            />
          ) : (
            <div className="space-y-2" data-testid="vehicles-list">
              {vehicles.map((v) => (
                <button
                  key={v.plate}
                  data-testid={`vehicle-card-${v.plate.replace(/\s+/g, "-").toLowerCase()}`}
                  onClick={() => setPlate(v.plate)}
                  className={cn(
                    "w-full rounded-lg border p-3 text-left transition hover:border-primary/60",
                    plate === v.plate ? "border-primary bg-primary/5" : "border-border bg-card"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-mono text-sm font-bold tracking-wider">
                      <Car className="size-4 text-primary" />
                      {v.plate}
                    </span>
                    <Badge variant="outline" className="rounded-sm text-[10px]">
                      {v.visit_count}x servis
                    </Badge>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {v.last_customer ?? "Umum"} · terakhir {formatDate(v.last_visit)} · {formatIDR(v.total_spent)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {v.last_tire ? (
                      <span className="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300">
                        <CircleDot className="size-3" /> {v.last_tire}
                      </span>
                    ) : null}
                    {v.last_oil ? (
                      <span className="inline-flex items-center gap-1 rounded-md border border-sky-500/30 bg-sky-500/10 px-1.5 py-0.5 text-[10px] text-sky-300">
                        <Droplet className="size-3" /> {v.last_oil}
                      </span>
                    ) : null}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail kendaraan */}
        <div className="xl:col-span-7">
          {!plate ? (
            <EmptyBlock
              title="Pilih kendaraan"
              description="Klik salah satu nomor polisi di sebelah kiri untuk melihat riwayat servisnya."
              className="h-full"
            />
          ) : detailQuery.isPending ? (
            <LoadingBlock />
          ) : detailQuery.isError ? (
            <ErrorBlock error={detailQuery.error} onRetry={() => void detailQuery.refetch()} />
          ) : detail ? (
            <div className="space-y-4" data-testid="vehicle-detail">
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2 font-heading text-base">
                    <Car className="size-4 text-primary" />
                    <span className="font-mono tracking-wider" data-testid="vehicle-detail-plate">
                      {detail.plate}
                    </span>
                    <Badge variant="outline" className="rounded-sm">
                      {detail.visit_count}x servis
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-3">
                    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-300">
                      <CircleDot className="size-3.5" /> Ban Terakhir
                    </p>
                    <p className="mt-1 text-sm font-semibold" data-testid="vehicle-last-tire">
                      {detail.last_tire ?? "Belum ada"}
                    </p>
                    {detail.last_tire_date ? (
                      <p className="text-xs text-muted-foreground">Dipasang {formatDate(detail.last_tire_date)}</p>
                    ) : null}
                  </div>
                  <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-3">
                    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-sky-300">
                      <Droplet className="size-3.5" /> Oli Terakhir
                    </p>
                    <p className="mt-1 text-sm font-semibold" data-testid="vehicle-last-oil">
                      {detail.last_oil ?? "Belum ada"}
                    </p>
                    {detail.last_oil_date ? (
                      <p className="text-xs text-muted-foreground">Diganti {formatDate(detail.last_oil_date)}</p>
                    ) : null}
                  </div>
                  <div className="rounded-lg bg-secondary/50 p-3">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Belanja</p>
                    <p className="mt-1 font-mono font-bold text-primary">{formatIDR(detail.total_spent)}</p>
                  </div>
                  <div className="rounded-lg bg-secondary/50 p-3">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">Pemilik / Terakhir</p>
                    <p className="mt-1 text-sm font-semibold">{detail.last_customer ?? "Umum"}</p>
                    <p className="text-xs text-muted-foreground">Kunjungan {formatDate(detail.last_visit)}</p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="font-heading text-base">Riwayat Servis</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {detail.services.map((s) => (
                    <div
                      key={s.id}
                      className="rounded-lg border border-border p-3"
                      data-testid={`vehicle-service-${s.invoice_number.toLowerCase()}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs text-muted-foreground">{s.invoice_number}</span>
                        <div className="flex items-center gap-2">
                          <PaymentMethodBadge method={s.payment_method} />
                          <TxStatusBadge status={s.status} />
                          <span className="font-mono text-sm font-bold">{formatIDR(s.total_amount)}</span>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(s.date)}</p>
                      <ul className="mt-2 space-y-0.5">
                        {s.details.map((d) => (
                          <li key={d.id} className="flex justify-between gap-2 text-xs">
                            <span className="min-w-0 truncate">
                              {d.product_name} <span className="text-muted-foreground">× {d.qty}</span>
                            </span>
                            <span className="shrink-0 font-mono text-muted-foreground">{formatIDR(d.subtotal)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
