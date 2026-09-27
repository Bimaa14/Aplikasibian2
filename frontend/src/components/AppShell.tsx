import { useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import {
  Archive,
  Calculator,
  Car,
  FileSpreadsheet,
  HandCoins,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  PackagePlus,
  ReceiptText,
  ShoppingCart,
  Truck,
  Users,
  Wallet,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { LoadingBlock } from "@/components/StateBlock";
import { endSession } from "@/lib/session";
import { useMe } from "@/lib/useMe";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/pos", label: "Kasir POS", icon: ShoppingCart, testid: "nav-pos" },
  { to: "/transaksi", label: "Transaksi", icon: ReceiptText, testid: "nav-transactions" },
  { to: "/kendaraan", label: "Riwayat Kendaraan", icon: Car, testid: "nav-vehicles" },
  { to: "/produk", label: "Produk", icon: Package, testid: "nav-products" },
  { to: "/stok-masuk", label: "Stok Masuk", icon: PackagePlus, testid: "nav-stock-in" },
  { to: "/pelanggan", label: "Pelanggan", icon: Users, testid: "nav-customers" },
  { to: "/distributor", label: "Distributor", icon: Truck, testid: "nav-suppliers" },
  { to: "/piutang-hutang", label: "Piutang & Hutang", icon: HandCoins, testid: "nav-debts" },
  { to: "/pengeluaran", label: "Pengeluaran", icon: Wallet, testid: "nav-expenses" },
  { to: "/laporan", label: "Laba Margin POS", icon: FileSpreadsheet, testid: "nav-reports" },
  { to: "/laporan-kas", label: "Laporan Kas & Pajak", icon: Calculator, testid: "nav-books" },
  { to: "/laporan-excel", label: "Laporan Excel", icon: FileSpreadsheet, testid: "nav-excel-reports" },
  { to: "/impor", label: "Impor & Pemeriksaan", icon: PackagePlus, testid: "nav-import" },
  { to: "/snapshot-stok", label: "Snapshot Stok (Ref)", icon: Archive, testid: "nav-stock-snapshot" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const me = useMe();
  return (
    <nav className="flex flex-col gap-1 px-3">
      {NAV.filter(n => me.data?.role === 'admin' || !['/laporan', '/laporan-kas', '/laporan-excel', '/impor', '/snapshot-stok'].includes(n.to)).map(({ to, label, icon: Icon, testid }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          data-testid={testid}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )
          }
        >
          <Icon className="size-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3 px-5 py-5">
      <div className="glow-amber grid size-9 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground">
        <Wrench className="size-5" />
      </div>
      <div>
        <p className="font-heading text-lg font-bold leading-none tracking-tight">BengKasir</p>
        <p className="mt-1 text-xs text-muted-foreground">POS &amp; Mini ERP Bengkel</p>
      </div>
    </div>
  );
}

function UserBox({ user }: { user: User }) {
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center gap-3 rounded-md bg-card px-3 py-2.5">
        <div className="grid size-8 shrink-0 place-items-center rounded-full bg-secondary text-sm font-bold">
          {user.name.charAt(0)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold" data-testid="sidebar-user-name">
            {user.name}
          </p>
          <Badge variant="outline" className="mt-0.5 h-4 rounded-sm px-1.5 text-[10px] uppercase tracking-wider">
            {user.role}
          </Badge>
        </div>
        <Button variant="ghost" size="icon-sm" data-testid="logout-button" onClick={() => endSession()} title="Keluar">
          <LogOut className="size-4" />
        </Button>
      </div>
    </div>
  );
}

export default function AppShell() {
  const me = useMe();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  if (me.isPending) {
    return (
      <div className="grid min-h-svh place-items-center bg-background text-foreground">
        <LoadingBlock label="Memuat sesi…" className="w-72" />
      </div>
    );
  }
  if (me.isError || !me.data) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* Sidebar desktop */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-sidebar lg:flex print:hidden">
        <Brand />
        <div className="flex-1 overflow-y-auto py-2">
          <NavLinks />
        </div>
        <UserBox user={me.data} />
      </aside>

      {/* Header mobile */}
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur lg:hidden print:hidden">
        <Button
          variant="ghost"
          size="icon"
          data-testid="mobile-nav-button"
          onClick={() => setMobileNavOpen(true)}
        >
          <Menu className="size-5" />
        </Button>
        <p className="font-heading font-bold">BengKasir</p>
        <div className="ml-auto flex items-center gap-2">
          <span className="max-w-28 truncate text-sm font-medium">{me.data.name}</span>
          <Button variant="ghost" size="icon-sm" data-testid="logout-button-mobile" onClick={() => endSession()}>
            <LogOut className="size-4" />
          </Button>
        </div>
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent side="left" className="w-64 p-0">
            <SheetTitle className="sr-only">Menu navigasi</SheetTitle>
            <Brand />
            <div className="overflow-y-auto pb-4">
              <NavLinks onNavigate={() => setMobileNavOpen(false)} />
            </div>
          </SheetContent>
        </Sheet>
      </header>

      <main className="lg:pl-60">
        <Outlet />
      </main>
    </div>
  );
}
