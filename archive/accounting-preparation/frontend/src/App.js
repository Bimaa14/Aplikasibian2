import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { Shell } from './accounting/components/Shell';
import Dashboard from './accounting/pages/Dashboard';
import DebtPage from './accounting/pages/DebtPage';
import EntriesPage from './accounting/pages/EntriesPage';
import ReportsPage from './accounting/pages/ReportsPage';
import SettingsPage from './accounting/pages/SettingsPage';
import '@fontsource/outfit/400.css';
import '@fontsource/outfit/500.css';
import '@fontsource/outfit/600.css';
import '@fontsource/outfit/700.css';
import '@fontsource/plus-jakarta-sans/400.css';
import '@fontsource/plus-jakarta-sans/500.css';
import '@fontsource/plus-jakarta-sans/600.css';
import '@fontsource/plus-jakarta-sans/700.css';
import '@fontsource/jetbrains-mono/500.css';
import './App.css';

export default function App() {
  return <BrowserRouter><Routes><Route element={<Shell />}><Route path="/" element={<Dashboard />} /><Route path="/piutang" element={<DebtPage key="receivable" kind="receivable" />} /><Route path="/hutang" element={<DebtPage key="payable" kind="payable" />} /><Route path="/transaksi" element={<EntriesPage />} /><Route path="/laporan" element={<ReportsPage />} /><Route path="/pengaturan" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes><Toaster position="top-right" theme="light" richColors /></BrowserRouter>;
}