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
    <div className="p-4 md:p-6">
      <div className="mb-4">
        <h1 className="font-heading text-2xl font-bold tracking-tight">Kode Referensi Laravel 11</h1>
        <p className="text-sm text-muted-foreground">
          Bundle Laravel 11 + Filament v3 + Livewire v3 + MySQL sesuai permintaan: perintah terminal, migration,
          model, komponen Livewire POS, dan widget Filament. Aplikasi demo di pod ini menjalankan logika yang sama.
        </p>
      </div>

      {bundleQuery.isPending ? (
        <LoadingBlock />
      ) : bundleQuery.isError ? (
        <ErrorBlock error={bundleQuery.error} onRetry={() => void bundleQuery.refetch()} />
      ) : files.length === 0 ? (
        <EmptyBlock title="Bundle kosong" description="Tidak ada berkas referensi ditemukan di server." />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          {/* Daftar berkas */}
          <Card className="lg:col-span-4 xl:col-span-3">
            <CardHeader>
              <CardTitle className="font-heading text-base">Berkas ({files.length})</CardTitle>
            </CardHeader>
            <CardContent className="max-h-[70vh] space-y-1 overflow-y-auto">
              {files.map((f) => (
                <button
                  key={f.path}
                  data-testid={`laravel-file-${f.path.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}
                  onClick={() => setSelected(f.path)}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors",
                    current?.path === f.path
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <FileCode2 className="mt-0.5 size-3.5 shrink-0" />
                  <span className="min-w-0">
                    <span className="block truncate font-mono font-semibold">{f.path}</span>
                    {f.description ? <span className="mt-0.5 block text-[11px] opacity-70">{f.description}</span> : null}
                  </span>
                </button>
              ))}
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
                <Download className="size-4" /> Unduh Semua (JSON)
              </Button>
            </CardContent>
          </Card>

          {/* Kode */}
          <Card className="lg:col-span-8 xl:col-span-9">
            <CardHeader className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <CardTitle className="truncate font-mono text-sm" data-testid="laravel-current-path">
                  {current?.path}
                </CardTitle>
                {current?.description ? (
                  <p className="mt-1 text-xs text-muted-foreground">{current.description}</p>
                ) : null}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="laravel-copy-button"
                  onClick={() => {
                    if (current) {
                      void navigator.clipboard.writeText(current.code);
                      toast.success("Kode disalin ke clipboard");
                    }
                  }}
                >
                  <Copy className="size-4" /> Salin
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
                  <Download className="size-4" /> Unduh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre
                data-testid="laravel-code-viewer"
                className="max-h-[70vh] overflow-auto rounded-lg border border-border bg-[#0d1117] p-4 font-mono text-xs leading-relaxed text-slate-200"
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
