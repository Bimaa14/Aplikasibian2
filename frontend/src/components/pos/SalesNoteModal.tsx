import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileDown, Printer, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buildSalesNoteDocument, loadNoteSettings, NOTE_SETTINGS_KEY } from "@/lib/sales-note";
import type { NoteSettings } from "@/lib/sales-note";
import type { Transaction } from "@/lib/types";

const waitForPaint = () => new Promise<void>((resolve) => {
  let frameId = 0;
  const finish = () => {
    window.clearTimeout(timer);
    window.cancelAnimationFrame(frameId);
    resolve();
  };
  const timer = window.setTimeout(finish, 150);
  frameId = window.requestAnimationFrame(() => { frameId = window.requestAnimationFrame(finish); });
});

export default function SalesNoteModal({ transaction, open, autoPrint = false, onOpenChange }: {
  transaction: Transaction | null;
  open: boolean;
  autoPrint?: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [settings, setSettings] = useState(loadNoteSettings);
  const [showSettings, setShowSettings] = useState(false);
  const [ready, setReady] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);
  const [printError, setPrintError] = useState<string | null>(null);
  const [previewHeight, setPreviewHeight] = useState(540);
  const frame = useRef<HTMLIFrameElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const readyDocument = useRef<Document | null>(null);
  const documentVersion = useRef(0);
  const autoPrintedTransaction = useRef<string | null>(null);
  const html = useMemo(() => transaction ? buildSalesNoteDocument(transaction, settings) : "", [transaction, settings]);

  useEffect(() => {
    documentVersion.current += 1;
    readyDocument.current = null;
    setReady(false);
    setPrinting(false);
    setPreviewError(null);
    setPrintError(null);
    return () => { documentVersion.current += 1; readyDocument.current = null; };
  }, [html, open]);

  function updateSettings(changes: Partial<NoteSettings>) {
    const next = { ...settings, ...changes };
    setSettings(next);
    try { localStorage.setItem(NOTE_SETTINGS_KEY, JSON.stringify(next)); }
    catch { toast.error("Pengaturan berlaku sekarang, tetapi tidak bisa disimpan di browser ini."); }
  }

  async function preparePreview() {
    const target = frame.current?.contentWindow;
    const doc = frame.current?.contentDocument;
    const version = documentVersion.current;
    if (!target || !doc || !open) return;
    try {
      await doc.fonts.ready;
      await waitForPaint();
      if (version !== documentVersion.current || frame.current?.contentDocument !== doc) return;
      setPreviewHeight(Math.max(doc.body.scrollHeight, settings.paper === "full" ? 1056 : 528) + 2);
      readyDocument.current = doc;
      setReady(true);
    } catch {
      if (version === documentVersion.current && frame.current?.contentDocument === doc) setPreviewError("Pratinjau gagal dimuat. Tutup nota lalu cetak ulang.");
    }
  }

  const print = useCallback(async (destination: 'printer' | 'pdf') => {
    const target = frame.current?.contentWindow;
    const doc = frame.current?.contentDocument;
    const version = documentVersion.current;
    if (!target || !doc || !open || !ready || printing || readyDocument.current !== doc) return;
    setPrinting(true);
    setPrintError(null);
    try {
      await doc.fonts.ready;
      if (version !== documentVersion.current || frame.current?.contentDocument !== doc) return;
      doc.getElementById('note-printer-page')?.remove();
      if (destination === 'printer') {
        // The printer driver selects the physical form and orientation.
        const style = doc.createElement('style');
        style.id = 'note-printer-page';
        style.textContent = '@page { size: auto; margin: 0; }';
        doc.head.appendChild(style);
      }
      await waitForPaint();
      if (version !== documentVersion.current || frame.current?.contentDocument !== doc) return;
      target.focus();
      target.print();
    } catch {
      if (version === documentVersion.current) {
        const message = "Transaksi sudah tersimpan. Jendela cetak gagal dibuka; pilih Cetak Nota untuk mencoba lagi.";
        setPrintError(message);
        toast.error(message);
      }
    } finally {
      if (version === documentVersion.current) {
        setPrinting(false);
        closeButton.current?.focus({ preventScroll: true });
      }
    }
  }, [open, ready, printing]);

  useEffect(() => {
    if (!autoPrint || !open || !ready || !transaction || autoPrintedTransaction.current === transaction.id || readyDocument.current !== frame.current?.contentDocument) return;
    autoPrintedTransaction.current = transaction.id;
    void print('printer');
  }, [autoPrint, open, ready, transaction, print]);

  if (!transaction) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[94dvh] w-[calc(100vw-1.5rem)] min-w-0 flex-col gap-3 overflow-hidden sm:max-w-[1040px]" data-testid="sales-note-dialog">
        <DialogHeader className="pr-8">
          <DialogTitle>Nota Penjualan</DialogTitle>
          <DialogDescription>{transaction.invoice_number} sudah tersimpan. Cetak ulang menggunakan transaksi yang sama.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 max-w-full items-center gap-2">
            <Label htmlFor="note-paper">Kertas</Label>
            <select id="note-paper" className="min-w-0 rounded-md border border-border bg-background px-3 py-2 text-sm" value={settings.paper}
              onChange={(event) => updateSettings({ paper: event.target.value === "full" ? "full" : "half" })}>
              <option value="half">9,5 × 5,5 inci · setengah lembar</option>
              <option value="full">9,5 × 11 inci · satu lembar</option>
            </select>
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowSettings(!showSettings)} aria-expanded={showSettings}>
            <Settings2 /> Identitas toko
          </Button>
        </div>
        {showSettings && <div className="grid shrink-0 grid-cols-1 gap-3 rounded-lg border border-border p-3 sm:grid-cols-2">
          {([
            ["name", "Nama toko", 80], ["address", "Alamat", 160], ["phone", "Telepon / HP", 100], ["footer", "Catatan di bawah nota", 180],
          ] as const).map(([key, label, maxLength]) => <div className="space-y-1" key={key}>
            <Label htmlFor={`note-${key}`}>{label}</Label>
            <Input id={`note-${key}`} value={settings[key]} maxLength={maxLength}
              placeholder={key === "phone" ? "Isi nomor telepon toko" : undefined}
              onChange={(event) => updateSettings({ [key]: event.target.value })} />
          </div>)}
          <p className="text-xs text-muted-foreground sm:col-span-2">Tersimpan di browser komputer ini dan dipakai saat mencetak nota.</p>
        </div>}
        {printError ? <p role="alert" data-testid="sales-note-print-error" className="text-sm text-destructive">{printError}</p> : null}
        <div className="min-h-0 min-w-0 flex-1 overflow-auto rounded-lg border border-border bg-muted/30 p-3" data-testid="sales-note-preview" aria-busy={!ready && !previewError}>
          {previewError ? <p role="alert" className="mb-3 text-sm text-destructive">{previewError}</p>
            : !ready ? <p role="status" className="mb-3 text-sm text-muted-foreground">Menyiapkan nota...</p> : null}
          <iframe ref={frame} title="Pratinjau nota penjualan" srcDoc={html} sandbox="allow-same-origin allow-modals"
            className="mx-auto block border-0 bg-white shadow-sm" style={{ width: "241.3mm", height: previewHeight }}
            onLoad={() => void preparePreview()}
            onError={() => setPreviewError("Pratinjau gagal dimuat. Tutup nota lalu cetak ulang.")} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-xl text-xs leading-relaxed text-muted-foreground">Cetak Nota: pilih printer, Portrait, dan form {settings.paper === 'half' ? '9,5 × 5,5 inci. ' : '9,5 × 11 inci. '}Skala 100%, matikan header/footer browser. Simpan PDF: pilih Save as PDF; ukuran mengikuti pilihan kertas di atas.</p>
          <div className="flex flex-wrap gap-2">
            <Button ref={closeButton} variant="outline" data-testid="close-receipt-btn" onClick={() => onOpenChange(false)}>Tutup</Button>
            <Button variant="outline" data-testid="save-note-pdf-btn" onClick={() => void print('pdf')} disabled={!ready || printing}><FileDown /> Simpan PDF</Button>
            <Button data-testid="print-receipt-btn" onClick={() => void print('printer')} disabled={!ready || printing}><Printer /> Cetak Nota</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
