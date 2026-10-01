import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
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
      <div className="relative hidden lg:block entry-fade">
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
          <div className="mb-auto flex items-center gap-4 pt-8">
            <img src={`${import.meta.env.BASE_URL}LOGOWEB-removebg-preview.png`} alt="Logo Perkasa Jaya" className="h-32 w-auto shrink-0 object-contain drop-shadow-sm" />
            <p className="font-heading text-3xl font-bold tracking-tight text-amber-300 drop-shadow-md">PERKASA JAYA</p>
          </div>
        </div>
      </div>

      {/* Form kanan */}
      <div className="relative flex items-center justify-center p-6 pt-20 entry-fade-delayed">
        <div className="absolute right-6 top-6"><ThemeToggle compact /></div>
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src={`${import.meta.env.BASE_URL}LOGOWEB-removebg-preview.png`} alt="Logo Perkasa Jaya" className="h-16 w-auto shrink-0 object-contain drop-shadow-sm" />
            <p className="font-heading text-xl font-bold text-primary">PERKASA JAYA</p>
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
