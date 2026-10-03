import { describe, expect, it } from 'vitest';
import type { Product } from './types';
import { mechanicFeeTotal } from './pos-pricing';

function service(price: number): Product {
  return { id: 's', sku: 'S', name: 'SERVICE', type: 'jasa', category: 'SERVICE',
    selling_price: price, cost_price: 0, service_fee: 0, stock: 0,
    brand: '', size: '', owner: 'bian', tax: 0 };
}

describe('Excel SERVICE fee preview', () => {
  it('uses the discounted cash total and the original cash price for tempo', () => {
    const lines = [{ product: service(100000), qty: 3, price: 120000, discount: 15000 }];
    expect(mechanicFeeTotal(lines)).toBe(172500);
    expect(mechanicFeeTotal(lines, 0, true)).toBe(150000);
  });

  it('keeps a half-cent when the literal Excel formula divides an odd cent', () => {
    expect(mechanicFeeTotal([{ product: service(0.03), qty: 1, price: 0.03, discount: 0 }])).toBe(0.015);
  });

  it('uses the DATABASE fee per unit for other item names', () => {
    const product = { ...service(100000), name: 'SPOORING', service_fee: 10000 };
    expect(mechanicFeeTotal([{ product, qty: 3, price: 120000, discount: 15000 }], 0, true)).toBe(30000);
  });
});
