import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { BadgeCheck, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPost } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { beginSession } from "@/lib/session";
import { useMe } from "@/lib/useMe";
import type { User } from "@/lib/types";

// Foto asli storefront Perkasa Jaya (Dunlop Shop). Disimpan lokal di /public agar tetap
// tampil saat deployment offline (LAN, tanpa internet).
const HERO_IMAGE = "/storefront-login.jpg";

export default function LoginPage() {
  const navigate = useNavigate();
  const me = useMe();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => apiPost<User>("/auth/login", { username: username.trim(), password }),
    onSuccess: () => {
      beginSession(); // hapus cache react-query milik sesi sebelumnya
      toast.success("Selamat bekerja!");
      navigate("/", { replace: true });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  if (me.data) return <Navigate to="/" replace />;

  return (
    <div className="grid min-h-svh bg-background text-foreground lg:grid-cols-2">
      {/* Hero kiri — workshop */}
      <div className="relative hidden lg:block">
        <img
          src={HERO_IMAGE}
          alt="Storefront Dunlop Shop — Perkasa Jaya"
          className="absolute inset-0 size-full object-cover"
          style={{ objectPosition: "84% 32%" }}
        />
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(180deg, rgba(11,15,23,0.35) 0%, rgba(11,15,23,0.72) 55%, rgba(11,15,23,0.94) 100%)" }}
        />
        <div className="relative flex h-full flex-col justify-end p-10">
          <div className="mb-auto flex items-center gap-3 pt-8">
            <div className="glow-amber grid size-10 place-items-center rounded-md bg-primary text-primary-foreground">
              <Wrench className="size-5" />
            </div>
            <p className="font-heading text-xl font-bold tracking-tight">BengKasir</p>
          </div>
          <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight">
            POS &amp; Mini ERP untuk
            <span className="text-primary"> bengkel ban &amp; servis otomotif</span>
          </h1>
          <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <BadgeCheck className="size-4 text-primary" /> Kasir cepat dengan struk thermal 80mm
            </li>
            <li className="flex items-center gap-2">
              <BadgeCheck className="size-4 text-primary" /> Piutang pelanggan (tempo) &amp; hutang distributor otomatis
            </li>
            <li className="flex items-center gap-2">
              <BadgeCheck className="size-4 text-primary" /> Laba kotor/bersih: komisi montir &amp; pengeluaran terhitung
            </li>
          </ul>
        </div>
      </div>

      {/* Form kanan */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="glow-amber grid size-9 place-items-center rounded-md bg-primary text-primary-foreground">
              <Wrench className="size-5" />
            </div>
            <p className="font-heading text-lg font-bold">BengKasir</p>
          </div>
          <h2 className="font-heading text-2xl font-bold tracking-tight">Masuk ke Kasir</h2>
          <p className="mt-1 text-sm text-muted-foreground">Gunakan akun kasir atau admin bengkel Anda.</p>

          <form
            className="mt-6 space-y-4"
            data-testid="login-form"
            onSubmit={(e) => {
              e.preventDefault();
              loginMutation.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="login-username">Username</Label>
              <Input
                id="login-username"
                data-testid="login-username-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="mis. admin"
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                data-testid="login-password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </div>
            <Button
              type="submit"
              className="w-full"
              data-testid="login-submit-button"
              disabled={loginMutation.isPending}
            >
              {loginMutation.isPending ? "Memproses…" : "Masuk"}
            </Button>
          </form>

          <div data-testid="login-account-info" className="mt-6 rounded-lg border border-border bg-card p-3 text-xs leading-relaxed text-muted-foreground">Akun admin dan kasir memakai password terpisah. Gunakan kredensial yang diberikan pemilik; password tidak ditampilkan di halaman publik.</div>
        </div>
      </div>
    </div>
  );
}
