import axios from 'axios';
import { useCallback, useEffect, useState } from 'react';

if (!process.env.REACT_APP_BACKEND_URL) throw new Error('REACT_APP_BACKEND_URL belum diatur');
export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`, timeout: 20000 });
export const rupiah = (value: number = 0) => `Rp ${new Intl.NumberFormat('id-ID').format(value)}`;
export const shortMoney = (value: number) => Math.abs(value) >= 1000000 ? `${(value / 1000000).toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt` : `${(value / 1000).toLocaleString('id-ID')} rb`;
export const dateLabel = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
export const monthLabel = (value: string) => new Date(`${value}-01T12:00:00`).toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
export const initialMonth = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Jakarta' }).slice(0, 7);
export const makeId = () => globalThis.crypto.randomUUID();
export const errorMessage = (e: any) => {
  const detail = e.response?.data?.detail;
  return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg.replace('Value error, ', '')).join(' ') : 'Server belum dapat dihubungi. Periksa koneksi lalu coba lagi.';
};

export function useLoad<T = any>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion(v => v + 1), []);
  useEffect(() => {
    window.addEventListener('online', reload);
    window.addEventListener('focus', reload);
    return () => { window.removeEventListener('online', reload); window.removeEventListener('focus', reload); };
  }, [reload]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api.get(path, { signal: controller.signal }).then(r => setData(r.data)).catch(e => {
      if (!axios.isCancel(e)) setError(errorMessage(e));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, version]);
  return { data, loading, error, reload };
}

export function download(name: string, content: string, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([type.includes('csv') ? '\ufeff' : '', content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const csv = (rows: any[][]) => rows.map(row => row.map(value => {
  let str = String(value ?? '');
  if (typeof value === 'string' && /^[=+\-@\t\r]/.test(str)) str = `'${str}`;
  return `"${str.replace(/"/g, '""')}"`;
}).join(';')).join('\r\n');

export type Debt = {
  id: string; kind: 'receivable' | 'payable'; party: string; reference: string; description: string;
  total: number; hpp: number; paid_amount: number; remaining: number;
  status: 'unpaid' | 'partial' | 'paid' | 'void'; issued_date: string; due_date: string;
  days_overdue: number; days_remaining: number; due_label: string; aging_bucket: string | null;
  return_date?: string; return_reason?: string; refund_amount: number;
  payments: { id: string; amount: number; method: string; payment_date: string; note: string }[];
};
export const statusLabel = { unpaid: 'Belum dibayar', partial: 'Dibayar sebagian', paid: 'Lunas', void: 'Retur / Void' };