import type { PaymentMethod } from './types';

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Tunai', edc: 'EDC', transfer_bca: 'Transfer BCA', transfer_bri: 'Transfer BRI',
  transfer_bni: 'Transfer BNI', qris: 'QRIS', credit: 'Tempo (Kredit)',
};
export const PAYMENT_OPTIONS = Object.entries(PAYMENT_LABELS) as [PaymentMethod, string][];
