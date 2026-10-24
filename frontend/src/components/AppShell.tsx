import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
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
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { LoadingBlock } from "@/components/StateBlock";
import { endSession } from "@/lib/session";
import { useMe } from "@/lib/useMe";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV_GROUPS = [
  {
    label: "Operasional",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
      { to: "/pos", label: "Kasir POS", icon: ShoppingCart, testid: "nav-pos" },
      { to: "/transaksi", label: "Transaksi", icon: ReceiptText, testid: "nav-transactions" },
      { to: "/kendaraan", label: "Riwayat Kendaraan", icon: Car, testid: "nav-vehicles" },
      { to: "/piutang-hutang", label: "Piutang & Hutang", icon: HandCoins, testid: "nav-debts" },
      { to: "/pengeluaran", label: "Pengeluaran", icon: Wallet, testid: "nav-expenses" },
    ],
  },
  {
    label: "Data bengkel",
    items: [
      { to: "/produk", label: "Produk", icon: Package, testid: "nav-products" },
      { to: "/stok-masuk", label: "Stok Masuk", icon: PackagePlus, testid: "nav-stock-in" },
      { to: "/pelanggan", label: "Pelanggan", icon: Users, testid: "nav-customers" },
      { to: "/distributor", label: "Distributor", icon: Truck, testid: "nav-suppliers" },
    ],
  },
  {
    label: "Laporan & referensi",
    items: [
      { to: "/laporan", label: "Laporan Bulanan Excel", icon: FileSpreadsheet, testid: "nav-reports" },
      { to: "/laporan-kas", label: "Laporan Kas & Pajak", icon: Calculator, testid: "nav-books" },
      { to: "/laporan-excel", label: "Laporan Excel", icon: FileSpreadsheet, testid: "nav-excel-reports" },
      { to: "/impor", label: "Impor & Pemeriksaan", icon: PackagePlus, testid: "nav-import" },
      { to: "/snapshot-stok", label: "Snapshot Stok (Ref)", icon: Archive, testid: "nav-stock-snapshot" },
    ],
    adminOnly: true,
  },
];

const RAIL_CONTROL = "min-h-11 border-[#8295ad] bg-transparent text-[#e2e8f0] hover:bg-[#26374d] hover:text-white focus-visible:ring-[#f1bc3c]";

function NavLinks({ user, onNavigate }: { user: User; onNavigate?: () => void }) {
  return (
    <nav aria-label="Navigasi utama" className="space-y-5 px-3 pb-5">
      {NAV_GROUPS.filter((group) => !group.adminOnly || user.role === "admin").map((group) => (
        <div key={group.label}>
          <p className="mb-2 px-3 text-xs font-medium text-[#bac6d6]">{group.label}</p>
          <div className="space-y-1">
            {group.items.map(({ to, label, icon: Icon, testid }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                data-testid={testid}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-[0.875rem] font-medium leading-5 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f1bc3c]",
                    isActive
                      ? "bg-[#f1bc3c] text-[#142234]"
                      : "text-[#d1dbe7] hover:bg-[#26374d] hover:text-white active:bg-[#314357]"
                  )
                }
              >
                <Icon aria-hidden="true" className="size-[18px] shrink-0" strokeWidth={1.8} />
                <span className="min-w-0 break-words">{label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="px-6 pb-6 pt-5">
      <img
        src={`${import.meta.env.BASE_URL}LOGOWEB-removebg-preview.png`}
        alt="Perkasa Jaya, Dunlop Shop"
        className="h-[104px] w-[176px] max-w-full object-contain"
        width="176"
        height="104"
      />
      <p className="mt-1 text-xs leading-5 text-[#bac6d6]">Kasir &amp; pembukuan bengkel</p>
    </div>
  );
}

function UserBox({ user }: { user: User }) {
  return (
    <div className="border-t border-[#314357] px-4 py-4">
      <div className="flex items-center gap-3">
        <div aria-hidden="true" className="grid size-9 shrink-0 place-items-center rounded-md bg-[#314357] text-sm font-semibold text-white">
          {user.name.charAt(0)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold leading-5 text-white" data-testid="sidebar-user-name">
            {user.name}
          </p>
          <p className="mt-0.5 text-xs text-[#bac6d6]" data-testid="sidebar-user-role">{user.role === "admin" ? "Admin" : "Kasir"}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={cn("size-11 shrink-0", RAIL_CONTROL)}
          data-testid="logout-button"
          onClick={() => endSession()}
          aria-label="Keluar dari akun"
          title="Keluar dari akun"
        >
          <LogOut aria-hidden="true" className="size-[18px]" />
        </Button>
      </div>
    </div>
  );
}

export default function AppShell() {
  const me = useMe();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  if (me.isPending) {
    return (
      <div className="grid min-h-svh place-items-center bg-background text-foreground">
        <LoadingBlock label="Memuat sesi..." className="w-72 max-w-[calc(100vw-32px)]" />
      </div>
    );
  }
  if (me.isError || !me.data) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-svh bg-background text-foreground">
      <a
        href="#main-content"
        data-testid="skip-to-content"
        className="sr-only fixed left-4 top-3 z-[100] rounded-md bg-[#f1bc3c] px-4 py-3 font-semibold text-[#142234] focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-[#142234]"
        onClick={(event) => {
          event.preventDefault();
          const main = document.getElementById("main-content");
          main?.focus();
          main?.scrollIntoView();
        }}
      >
        Lewati ke isi halaman
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-[#314357] bg-[#142234] lg:flex print:hidden">
        <Brand />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <NavLinks user={me.data} />
        </div>
        <div className="px-4 pb-4 pt-2"><ThemeToggle className={RAIL_CONTROL} /></div>
        <UserBox user={me.data} />
      </aside>

      <header className="sticky top-0 z-40 flex min-h-16 items-center gap-2 border-b border-[#314357] bg-[#142234] px-3 py-2 text-white lg:hidden print:hidden">
        <Button
          type="button"
          variant="ghost"
          className={cn("h-11 gap-2 px-3", RAIL_CONTROL)}
          data-testid="mobile-nav-button"
          aria-controls="mobile-navigation"
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen(true)}
        >
          <Menu aria-hidden="true" className="size-[18px]" />
          Menu
        </Button>
        <p className="min-w-0 flex-1 font-heading text-base font-semibold leading-5">Perkasa Jaya</p>
        <ThemeToggle compact className={RAIL_CONTROL} />
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent
            id="mobile-navigation"
            side="left"
            showCloseButton={false}
            className="gap-0 border-[#314357] bg-[#142234] p-0 text-white"
            style={{ width: "min(300px, calc(100vw - 24px))", maxWidth: "calc(100vw - 24px)" }}
            data-testid="mobile-nav-drawer"
          >
            <SheetTitle className="sr-only">Menu Perkasa Jaya</SheetTitle>
            <Brand />
            <SheetClose
              data-testid="mobile-nav-close"
              render={<Button type="button" variant="ghost" size="icon" className={cn("absolute right-3 top-4 size-11", RAIL_CONTROL)} aria-label="Tutup menu" />}
            >
              <X aria-hidden="true" className="size-5" />
            </SheetClose>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <NavLinks user={me.data} onNavigate={() => setMobileNavOpen(false)} />
            </div>
            <div className="px-4 pb-4 pt-2"><ThemeToggle className={RAIL_CONTROL} /></div>
            <UserBox user={me.data} />
          </SheetContent>
        </Sheet>
      </header>

      <main id="main-content" tabIndex={-1} className="min-w-0 outline-offset-[-4px] focus-visible:outline-2 focus-visible:outline-ring lg:pl-[248px]">
        <div key={location.pathname} className="min-h-[calc(100svh-64px)] min-w-0 lg:min-h-svh">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
