import type { Product } from './types';

/** Allocate invoice discounts after item discounts, using the same cents as checkout. */
export function mechanicFeeTotal(lines: { product: Product; qty: number; price: number; discount: number }[], invoiceDiscount: number) {
  const net = lines.map(l => Math.round(l.price * 100) * l.qty - Math.round(l.discount * 100));
  const total = net.reduce((sum, amount) => sum + amount, 0);
  const discount = Math.round(invoiceDiscount * 100);
  if (net.some(amount => !Number.isFinite(amount) || amount < 0) || !Number.isFinite(discount) || discount < 0 || discount > total) return 0;
  const allocated = net.map(amount => total ? Math.floor(discount * amount / total) : 0);
  const order = net.map((amount, index) => ({ index, remainder: total ? discount * amount % total : 0 }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (const { index } of order.slice(0, discount - allocated.reduce((sum, amount) => sum + amount, 0))) allocated[index]++;
  return lines.reduce((sum, line, i) => sum + (line.product.name.trim().toUpperCase() === 'SERVICE'
    ? Math.floor((net[i] - allocated[i] + 1) / 2)
    : Math.round(line.product.service_fee * 100) * line.qty), 0) / 100;
}
