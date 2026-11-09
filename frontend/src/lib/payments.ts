import type { NonCashMethod, PaymentMethod } from './types';

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Tunai',
  edc: 'EDC',
  transfer_bca: 'Transfer BCA',
  transfer_bri: 'Transfer BRI',
  transfer_bni: 'Transfer BNI',
  qris: 'QRIS',
  mix: 'Mix (Tunai + Transfer)',
  credit: 'Tempo (Kredit)',
};

export const PAYMENT_OPTIONS = Object.entries(PAYMENT_LABELS) as [PaymentMethod, string][];

export const NON_CASH_OPTIONS: [NonCashMethod, string][] = [
  ['transfer_bca', 'Transfer BCA'],
  ['transfer_bri', 'Transfer BRI'],
  ['transfer_bni', 'Transfer BNI'],
  ['edc', 'EDC'],
  ['qris', 'QRIS'],
];

export function formatPaymentMethodDetail(opts: {
  method?: string | null;
  cash_amount?: number | null;
  transfer_amount?: number | null;
  transfer_method?: string | null;
  formatMoney?: (n: number) => string;
}): string {
  const { method, cash_amount, transfer_amount, transfer_method, formatMoney } = opts;
  if (!method) return '-';
  const fmt = formatMoney ?? ((n: number) => `Rp ${Math.round(n).toLocaleString('id-ID')}`);
  if (method === 'mix') {
    const tfLabel =
      PAYMENT_LABELS[(transfer_method || 'transfer_bca') as PaymentMethod] ||
      (transfer_method === 'transfer' ? 'Transfer lainnya' : transfer_method || 'Transfer');
    if (cash_amount != null && transfer_amount != null) {
      return `Mix (Tunai ${fmt(cash_amount)} + ${tfLabel} ${fmt(transfer_amount)})`;
    }
    return `Mix (Tunai + ${tfLabel})`;
  }
  return PAYMENT_LABELS[method as PaymentMethod] || (method === 'transfer' ? 'Transfer lainnya' : method);
}
