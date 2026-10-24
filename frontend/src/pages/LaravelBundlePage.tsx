import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Download, FileCode2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import type { LaravelBundleFile } from "@/lib/types";
import { cn } from "@/lib/utils";

function downloadFile(filename: string, content: string, type = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function LaravelBundlePage() {
  const bundleQuery = useQuery({
    queryKey: ["laravel-bundle"],
    queryFn: () => apiGet<LaravelBundleFile[]>("/laravel-bundle"),
  });
  const files = bundleQuery.data ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  const current = files.find((f) => f.path === selected) ?? files[0] ?? null;

  return (
    <div className="page-workspace space-y-5">
      <div className="page-heading">
        <div className="min-w-0">
        <h1 data-testid="laravel-page-title" className="font-heading text-2xl font-bold tracking-tight">Kode referensi Laravel 11</h1>
        <p className="text-sm text-muted-foreground">
          Pilih berkas untuk membaca, menyalin, atau mengunduh kode referensi Laravel 11,
          Filament v3, Livewire v3, dan MySQL.
        </p>
        </div>
      </div>

      {bundleQuery.isPending ? (
        <LoadingBlock />
      ) : bundleQuery.isError ? (
        <ErrorBlock error={bundleQuery.error} onRetry={() => void bundleQuery.refetch()} />
      ) : files.length === 0 ? (
        <EmptyBlock title="Bundle kosong" description="Tidak ada berkas referensi ditemukan di server." />
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-12">
          {/* Daftar berkas */}
          <Card className="min-w-0 self-start xl:col-span-4">
            <CardHeader>
              <CardTitle className="font-heading text-base">Berkas ({files.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-88 space-y-2 overflow-y-auto" aria-label="Daftar berkas referensi">
              {files.map((f) => (
                <button
                  key={f.path}
                  data-testid={`laravel-file-${f.path.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}
                  onClick={() => setSelected(f.path)}
                  aria-pressed={current?.path === f.path}
                  className={cn(
                    "flex min-h-11 w-full items-start gap-3 rounded-md px-3 py-3 text-left text-sm transition-colors",
                    current?.path === f.path
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <FileCode2 className="mt-0.5 size-4 shrink-0" />
                  <span className="min-w-0">
                    <span className="block break-all font-mono text-xs font-semibold">{f.path}</span>
                    {f.description ? <span className="mt-1 block text-xs leading-relaxed">{f.description}</span> : null}
                  </span>
                </button>
              ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-3 w-full"
                data-testid="laravel-download-all-button"
                onClick={() => {
                  downloadFile("laravel-bundle.json", JSON.stringify(files, null, 2), "application/json");
                  toast.success("Bundle Laravel diunduh (laravel-bundle.json)");
                }}
              >
                <Download className="size-4" /> Unduh semua berkas (JSON)
              </Button>
            </CardContent>
          </Card>

          {/* Kode */}
          <Card className="min-w-0 xl:col-span-8">
            <CardHeader className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 w-full">
                <CardTitle className="break-all font-mono text-sm" data-testid="laravel-current-path">
                  {current?.path}
                </CardTitle>
                {current?.description ? (
                  <p className="mt-1 text-xs text-muted-foreground">{current.description}</p>
                ) : null}
              </div>
              <div className="report-actions flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="laravel-copy-button"
                  onClick={async () => {
                    if (current) {
                      try {
                        await navigator.clipboard.writeText(current.code);
                        toast.success("Kode disalin ke clipboard");
                      } catch {
                        toast.error("Kode gagal disalin. Gunakan Unduh berkas untuk menyimpannya.");
                      }
                    }
                  }}
                >
                  <Copy className="size-4" /> Salin kode
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="laravel-download-single-button"
                  onClick={() => {
                    if (current) {
                      downloadFile(current.path.split("/").pop() ?? "file.txt", current.code);
                      toast.success("Berkas diunduh");
                    }
                  }}
                >
                  <Download className="size-4" /> Unduh berkas
                </Button>
              </div>
            </CardHeader>
            <CardContent className="min-w-0">
              <pre
                data-testid="laravel-code-viewer"
                tabIndex={0}
                aria-label={`Kode ${current?.path ?? 'berkas terpilih'}`}
                className="max-h-[65dvh] max-w-full overflow-auto rounded-md border border-border bg-muted p-4 font-mono text-xs leading-relaxed text-foreground"
              >
                <code>{current?.code}</code>
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
