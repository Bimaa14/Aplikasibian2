import { useRef, useState } from "react";
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
  const detailRegion = useRef<HTMLDivElement>(null);

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
    <div className="page-workspace">
      <div className="page-heading">
        <div>
        <h1 className="font-heading text-2xl font-bold tracking-tight">Riwayat Kendaraan</h1>
        <p className="text-sm text-muted-foreground">
          Periksa kunjungan servis serta ban dan oli terakhir berdasarkan nomor polisi.
        </p>
        </div>
      </div>

      <div className="grid min-w-0 grid-cols-1 items-start gap-5 min-[1200px]:grid-cols-12">
        <div className="min-w-0 min-[1200px]:col-span-5">
          <div className="page-toolbar !mb-3">
          <div className="relative w-full min-w-0">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Cari nomor polisi kendaraan"
              data-testid="vehicle-search-input"
              className="pl-10 font-mono uppercase"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nomor polisi"
            />
          </div>
          </div>

          {listQuery.isPending ? (
            <LoadingBlock />
          ) : listQuery.isError ? (
            <ErrorBlock error={listQuery.error} onRetry={() => void listQuery.refetch()} />
          ) : vehicles.length === 0 ? (
            <EmptyBlock
              title={search.trim() ? "Nomor polisi tidak ditemukan" : "Belum ada riwayat kendaraan"}
              description={search.trim() ? "Coba nomor polisi lain atau hapus pencarian." : "Isi nomor polisi saat checkout di Kasir POS agar servis tercatat per kendaraan."}
            />
          ) : (
            <div className="data-panel max-h-[70dvh] divide-y divide-border overflow-y-auto" data-testid="vehicles-list">
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <h2 className="text-sm font-semibold">Daftar kendaraan</h2>
                <span className="text-sm text-muted-foreground" data-testid="vehicles-visible-count">{vehicles.length} kendaraan</span>
              </div>
              {vehicles.map((v) => (
                <button
                  key={v.plate}
                  data-testid={`vehicle-card-${v.plate.replace(/\s+/g, "-").toLowerCase()}`}
                  onClick={() => {
                    setPlate(v.plate);
                    if (window.matchMedia("(max-width: 1199px)").matches) {
                      detailRegion.current?.scrollIntoView({ block: "start" });
                    }
                  }}
                  aria-pressed={plate === v.plate}
                  aria-label={`Lihat riwayat kendaraan ${v.plate}`}
                  className={cn(
                    "min-h-11 w-full px-4 py-4 text-left transition-colors hover:bg-secondary/50",
                    plate === v.plate ? "bg-accent text-accent-foreground" : "bg-card"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-mono text-sm font-bold tracking-wider">
                      <Car aria-hidden="true" className="size-4 text-muted-foreground" />
                      {v.plate}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">{v.visit_count} kunjungan</span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    {v.last_customer ?? "Umum"} · terakhir {formatDate(v.last_visit)} · {formatIDR(v.total_spent)}
                  </p>
                  <div className="mt-2 space-y-1">
                    {v.last_tire ? (
                      <span className="flex items-start gap-2 text-xs text-muted-foreground">
                        <CircleDot aria-hidden="true" className="mt-0.5 size-3 shrink-0" /> {v.last_tire}
                      </span>
                    ) : null}
                    {v.last_oil ? (
                      <span className="flex items-start gap-2 text-xs text-muted-foreground">
                        <Droplet aria-hidden="true" className="mt-0.5 size-3 shrink-0" /> {v.last_oil}
                      </span>
                    ) : null}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div ref={detailRegion} role="region" aria-label="Detail riwayat kendaraan" data-testid="vehicle-detail-region" className="min-w-0 scroll-mt-24 min-[1200px]:col-span-7">
          {!plate ? (
            <EmptyBlock
              title="Pilih kendaraan"
              description="Pilih nomor polisi pada daftar kendaraan untuk melihat riwayat servisnya."
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
                    <Car aria-hidden="true" className="size-5 text-muted-foreground" />
                    <span className="font-mono text-lg tracking-wider" data-testid="vehicle-detail-plate">
                      {detail.plate}
                    </span>
                    <Badge variant="outline" className="rounded-sm">
                      {detail.visit_count} kunjungan
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-secondary/30 p-4">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                      <CircleDot aria-hidden="true" className="size-4" /> Ban terakhir
                    </p>
                    <p className="mt-2 text-sm font-semibold" data-testid="vehicle-last-tire">
                      {detail.last_tire ?? "Belum ada"}
                    </p>
                    {detail.last_tire_date ? (
                      <p className="text-xs text-muted-foreground">Dipasang {formatDate(detail.last_tire_date)}</p>
                    ) : null}
                  </div>
                  <div className="rounded-lg border border-border bg-secondary/30 p-4">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                      <Droplet aria-hidden="true" className="size-4" /> Oli terakhir
                    </p>
                    <p className="mt-2 text-sm font-semibold" data-testid="vehicle-last-oil">
                      {detail.last_oil ?? "Belum ada"}
                    </p>
                    {detail.last_oil_date ? (
                      <p className="text-xs text-muted-foreground">Diganti {formatDate(detail.last_oil_date)}</p>
                    ) : null}
                  </div>
                  <dl className="col-span-full space-y-3 border-t border-border pt-4 text-sm">
                    <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted-foreground">Total belanja</dt><dd className="font-mono font-semibold" data-testid="vehicle-total-spent">{formatIDR(detail.total_spent)}</dd></div>
                    <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted-foreground">Pelanggan terakhir</dt><dd className="font-medium">{detail.last_customer ?? "Umum"}</dd></div>
                    <div className="flex flex-wrap justify-between gap-2"><dt className="text-muted-foreground">Kunjungan terakhir</dt><dd>{formatDate(detail.last_visit)}</dd></div>
                  </dl>
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
                      className="rounded-lg border border-border p-4"
                      data-testid={`vehicle-service-${s.invoice_number.toLowerCase()}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs text-muted-foreground">{s.invoice_number}</span>
                        <div className="flex flex-wrap items-center gap-2">
                          <PaymentMethodBadge method={s.payment_method} />
                          <TxStatusBadge status={s.status} />
                          <span className="font-mono text-sm font-bold">{formatIDR(s.total_amount)}</span>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(s.date)}</p>
                      <ul className="mt-2 space-y-0.5">
                        {s.details.map((d) => (
                          <li key={d.id} className="flex flex-wrap justify-between gap-x-3 gap-y-1 py-1 text-sm">
                            <span className="min-w-0">
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
