import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, BookOpenText, ChevronRight, CircleHelp, LayoutDashboard, Menu, ReceiptText, Settings2, Wrench, X, PanelLeftClose, Wifi, WifiOff } from 'lucide-react';
import { useLoad } from '../lib';
import { Button } from '../../components/ui/button';

const nav = [
  { path: '/', name: 'Ringkasan', icon: LayoutDashboard, id: 'overview' },
  { path: '/piutang', name: 'Piutang pelanggan', icon: ArrowDownLeft, id: 'receivables' },
  { path: '/hutang', name: 'Hutang supplier', icon: ArrowUpRight, id: 'payables' },
  { path: '/transaksi', name: 'Catatan kas', icon: ReceiptText, id: 'entries' },
  { path: '/laporan', name: 'Laporan keuangan', icon: BookOpenText, id: 'reports' }
];

export const Shell = () => {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const health = useLoad('/health');
  const title = nav.find(n => n.path === location.pathname)?.name || 'Pengaturan';
  return <div className="app-shell">
    {open && <button data-testid="sidebar-overlay" className="sidebar-overlay" aria-label="Tutup navigasi" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <NavLink className="brand" to="/" data-testid="brand-home"><span className="brand-mark"><Wrench size={22} /></span><span>Beng<span className="brand-light">Kasir</span><small>APLIKASIBIAN</small></span></NavLink>
      <Button variant="ghost" className="mobile-close" data-testid="close-navigation" onClick={() => setOpen(false)}><X /></Button>
      <div className="workspace-card" data-testid="workspace-info"><div className="workspace-avatar">PJ</div><div><strong>Perkasa Jaya</strong><span>Administrasi bengkel</span></div><span className="workspace-dot" /></div>
      <span className="nav-caption" data-testid="navigation-caption">RUANG KERJA</span>
      <nav aria-label="Navigasi utama">{nav.map(n => <NavLink end={n.path === '/'} data-testid={`nav-${n.id}`} key={n.path} to={n.path} onClick={() => setOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><n.icon size={18} strokeWidth={1.7} /><span>{n.name}</span>{location.pathname === n.path && <ChevronRight size={14} />}</NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-tip" data-testid="accounting-tip"><span className="tip-icon"><BookOpenText size={17} /></span><strong>Angka jelas.<br />Usaha lebih terarah.</strong><p>Pantau tagihan dan kas bengkel dalam satu tempat.</p><NavLink to="/laporan" data-testid="sidebar-view-reports">Buka laporan <ArrowUpRight size={14} /></NavLink></div>
        <NavLink to="/pengaturan" data-testid="nav-settings" onClick={() => setOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Settings2 size={18} />Pengaturan</NavLink>
        <div className="sidebar-footer" data-testid="app-version"><span>BENGKASIR <b>•</b> PEMBUKUAN</span><span>v1.0</span></div>
      </div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumbs"><button className="mobile-menu" aria-label="Buka navigasi" data-testid="open-navigation" onClick={() => setOpen(true)}><Menu size={20} /></button><PanelLeftClose size={17} className="desktop-sidebar-icon" /><span className="breadcrumb-root">Ruang kerja</span><ChevronRight size={13} /><strong data-testid="breadcrumb-current">{title}</strong></div>
      <div className="topbar-right"><span className={`connection ${health.error ? 'disconnected' : ''}`} data-testid="connection-status">{health.error ? <WifiOff size={13} /> : <Wifi size={13} />}{health.loading ? 'Menghubungkan' : health.error ? 'Tidak terhubung' : 'Server terhubung'}</span><NavLink data-testid="help-link" aria-label="Informasi aplikasi" className="help-link" to="/pengaturan"><CircleHelp size={18} /></NavLink><span className="topbar-divider" /><NavLink to="/pengaturan" className="profile" data-testid="workspace-profile"><span>PJ</span><div><strong>Perkasa Jaya</strong><small>Workspace pembukuan</small></div></NavLink></div>
    </header><main className="main-content"><Outlet context={{ today: health.data?.today, timezone: health.data?.timezone }} /></main><footer className="page-footer" data-testid="page-footer"><span>© {new Date().getFullYear()} BengKasir · AplikasiBian</span><span>Dibuat untuk usaha yang terus bergerak.</span></footer></div>
  </div>;
};