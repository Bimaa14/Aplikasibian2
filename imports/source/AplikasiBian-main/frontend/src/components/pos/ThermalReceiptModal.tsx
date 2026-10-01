// Modal struk thermal 80mm — latar putih, font monospace, tepi gerigi, dan tombol print
// yang memicu window.print() dengan CSS @media print 80mm (index.css).
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { formatDateTime } from "@/lib/format";
import type { Transaction } from "@/lib/types";

function Barcode({ value }: { value: string }) {
  const bars = value.split("").flatMap((ch) => {
    const code = ch.charCodeAt(0);
    return [code % 3 + 1, (code >> 2) % 2 + 1];
  });
  return (
    <div className="mt-3 flex flex-col items-center gap-1">
      <div className="flex h-9 items-stretch gap-[2px]">
        {bars.map((w, i) => (
          <span
            key={i}
            style={{ width: `${w}px` }}
            className={i % 2 === 0 ? "bg-black" : "bg-transparent"}
          />
        ))}
      </div>
      <span className="text-[10px] tracking-[0.25em]">{value}</span>
    </div>
  );
}

function Dashed() {
  return <div className="my-2 border-t border-dashed border-black" />;
}

export default function ThermalReceiptModal({
  transaction,
  open,
  onOpenChange,
}: {
  transaction: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!transaction) return null;
  const credit = transaction.payment_method === "credit";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[350px] max-w-[94vw] gap-0 border-0 bg-transparent p-0 shadow-none"
        showCloseButton={false}
      >
        <div
          data-testid="thermal-receipt"
          className="receipt-print-root mx-auto w-[302px] bg-white font-mono text-[11px] leading-relaxed text-black shadow-2xl"
        >
          <div className="receipt-zigzag-top" />
          <div className="px-4 pb-4 pt-2">
            {transaction.status === "returned" ? (
              <p className="text-center font-bold text-red-700">** TRANS AKSI DIRETUR **</p>
            ) : null}
            <div className="text-center">
              <p className="text-sm font-bold tracking-wide">BENGKEL MAJU JAYA</p>
              <p className="text-[10px]">Ban &amp; Servis Otomotif</p>
              <p className="text-[10px]">Jl. Merdeka No. 12 — 0812-3456-7890</p>
            </div>
            <Dashed />
            <div className="space-y-0.5">
              <p>No&nbsp;&nbsp;: {transaction.invoice_number}</p>
              <p>Waktu: {formatDateTime(transaction.date)}</p>
              <p>Plg&nbsp;&nbsp;: {transaction.customer_name ?? "Umum"}</p>
              {transaction.vehicle_plate ? <p>Nopol: {transaction.vehicle_plate}</p> : null}
            </div>
            <Dashed />
            <div className="space-y-1.5">
              {transaction.details.map((d) => (
                <div key={d.id}>
                  <p className="font-semibold">{d.product_name}</p>
                  <div className="flex justify-between">
                    <span>
                      {d.qty} x {d.price.toLocaleString("id-ID")}
                    </span>
                    <span>{d.subtotal.toLocaleString("id-ID")}</span>
                  </div>
                </div>
              ))}
            </div>
            <Dashed />
            <div className="flex justify-between font-bold">
              <span>TOTAL</span>
              <span>Rp {transaction.total_amount.toLocaleString("id-ID")}</span>
            </div>
            <p>Bayar: {credit ? "TEMPO (KREDIT)" : "TUNAI"}</p>
            {credit && transaction.due_date ? (
              <p className="font-bold">Jatuh Tempo: {transaction.due_date.split("-").reverse().join("/")}</p>
            ) : null}
            <Dashed />
            <p className="text-center text-[10px]">Terima kasih & selamat berkendara</p>
            <p className="text-center text-[10px]">Barang yang sudah dipasang tidak dapat ditukar</p>
            <Barcode value={transaction.invoice_number} />
          </div>
          <div className="receipt-zigzag-bottom" />
        </div>
        <div className="mt-3 flex justify-center gap-2 print:hidden">
          <Button
            data-testid="print-receipt-btn"
            onClick={() => window.print()}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Cetak Struk (80mm)
          </Button>
          <Button variant="outline" data-testid="close-receipt-btn" onClick={() => onOpenChange(false)}>
            Tutup
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
