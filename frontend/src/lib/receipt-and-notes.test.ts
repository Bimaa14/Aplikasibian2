import { describe, expect, it } from 'vitest';
import { formatPaymentMethodDetail } from './payments';
import { buildReceiptHtml } from './receipt';
import { buildSalesNoteDocument, DEFAULT_NOTE_SETTINGS } from './sales-note';
import type { AccountsReceivable, DebtPayment, Transaction } from './types';

describe('Mix payment formatting and single-page receipt/notes', () => {
  it('formats mix payment detail with cash and transfer breakdown', () => {
    const label = formatPaymentMethodDetail({
      method: 'mix',
      cash_amount: 300000,
      transfer_amount: 200000,
      transfer_method: 'transfer_bca',
    });
    expect(label).toContain('Mix (Tunai');
    expect(label).toContain('300.000');
    expect(label).toContain('Transfer BCA');
    expect(label).toContain('200.000');
  });

  it('builds single-page Kwitansi HTML with Mix payment breakdown and page-break protection', () => {
    const debt: AccountsReceivable = {
      id: 'ar-1',
      transaction_id: 'tx-1',
      invoice_number: 'INV-261109-0001',
      customer_id: 'c-1',
      customer_name: 'Budi Santoso',
      amount: 600000,
      paid_amount: 450000,
      remaining: 150000,
      issued_date: '2026-11-09',
      due_date: '2026-11-23',
      days_overdue: 0,
      days_remaining: 14,
      due_label: 'Belum jatuh tempo (14 hari lagi)',
      aging_bucket: null,
      legacy_payment_history_missing: false,
      status: 'partial',
      payments: [],
    };
    const payment: DebtPayment = {
      id: 'pay-12345678',
      amount: 250000,
      payment_date: '2026-11-09',
      method: 'mix',
      cash_amount: 100000,
      transfer_amount: 150000,
      transfer_method: 'transfer_bri',
      note: 'Cicilan 1',
      profit_amount: 50000,
    };
    const html = buildReceiptHtml({
      kind: 'receivables',
      party: 'Budi Santoso',
      debt,
      payment,
      cumulativePaid: 450000,
    });
    expect(html).toContain('@page { size: auto; margin: 4mm 8mm; }');
    expect(html).toContain('page-break-inside: avoid');
    expect(html).toContain('max-height: 128mm');
    expect(html).toContain('Mix (Tunai Rp 100.000 + Transfer BRI Rp 150.000)');
    expect(html).toContain('Cicilan 1');
  });

  it('includes Mix breakdown on sales note and credit note', () => {
    const baseTx: Transaction = {
      id: 'tx-mix',
      invoice_number: 'INV-261109-0002',
      date: '2026-11-09T10:00:00Z',
      date_key: '2026-11-09',
      customer_id: 'c-1',
      customer_name: 'Budi Santoso',
      payment_method: 'mix',
      total_amount: 500000,
      cash_received: 500000,
      change_amount: 0,
      cash_amount: 300000,
      transfer_amount: 200000,
      transfer_method: 'transfer_bca',
      barang_amount: 500000,
      jasa_amount: 0,
      total_cost: 400000,
      service_fee: 0,
      total_profit: 100000,
      status: 'completed',
      due_date: null,
      vehicle_plate: 'D 1234 AB',
      details: [
        {
          id: 'd-1',
          transaction_id: 'tx-mix',
          product_id: 'p-1',
          product_name: 'Ban Bridgestone',
          product_sku: 'BR-01',
          product_type: 'barang',
          owner: 'bian',
          qty: 1,
          price: 500000,
          cost_price: 400000,
          service_fee: 0,
          subtotal: 500000,
        },
      ],
    };
    const salesHtml = buildSalesNoteDocument(baseTx, DEFAULT_NOTE_SETTINGS);
    expect(salesHtml).toContain('Mix (Tunai Rp300.000,00 + Transfer BCA Rp200.000,00)');

    const creditTx: Transaction = {
      ...baseTx,
      payment_method: 'credit',
      down_payment_amount: 200000,
      down_payment_method: 'mix',
      cash_amount: 50000,
      transfer_amount: 150000,
      transfer_method: 'qris',
      due_date: '2026-11-23',
      credit_term_days: 14,
    };
    const creditHtml = buildSalesNoteDocument(creditTx, DEFAULT_NOTE_SETTINGS);
    expect(creditHtml).toContain('Mix (Tunai Rp50.000,00 + QRIS Rp150.000,00)');
  });
});
