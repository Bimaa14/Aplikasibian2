import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { useMutation } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPost } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { beginSession } from "@/lib/session";
import { useMe } from "@/lib/useMe";
import type { User } from "@/lib/types";

const HERO_IMAGE = `${import.meta.env.BASE_URL}storefront-login.jpg`;
const LOGO_IMAGE = `${import.meta.env.BASE_URL}LOGOWEB-removebg-preview.png`;

export default function LoginPage() {
  const navigate = useNavigate();
  const me = useMe();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const loginMutation = useMutation({
    mutationFn: () => apiPost<User>("/auth/login", { username: username.trim(), password }),
    onSuccess: () => {
      beginSession();
      toast.success("Selamat bekerja!");
      navigate("/", { replace: true });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  if (me.data) return <Navigate to="/" replace />;

  return (
    <div className="grid min-h-svh bg-background text-foreground lg:grid-cols-[0.95fr_1.05fr]">
      <aside className="hidden min-h-svh flex-col bg-[#142234] text-white lg:flex" aria-label="Perkasa Jaya">
        <div className="px-10 py-7 xl:px-12">
          <img src={LOGO_IMAGE} alt="Perkasa Jaya, Dunlop Shop" className="h-28 w-52 object-contain" width="208" height="112" />
        </div>
        <div className="relative min-h-72 flex-1">
          <img
            src={HERO_IMAGE}
            alt="Bengkel Perkasa Jaya dengan papan Dunlop Shop"
            className="absolute inset-0 size-full object-cover"
            style={{ objectPosition: "72% 38%" }}
          />
        </div>
        <div className="px-10 py-9 xl:px-12 xl:py-10">
          <p className="max-w-sm font-heading text-[clamp(1.6rem,2.5vw,2.3rem)] font-semibold leading-tight">Kasir &amp; pembukuan<br />Perkasa Jaya.</p>
          <p className="mt-3 text-sm leading-6 text-[#d1dbe7]">Penjualan, stok, dan laporan bengkel.</p>
        </div>
      </aside>

      <main className="relative flex min-w-0 flex-col lg:items-center lg:justify-center">
        <div className="flex items-center justify-between gap-4 bg-[#142234] px-6 py-3 lg:absolute lg:right-8 lg:top-7 lg:bg-transparent lg:p-0">
          <img src={LOGO_IMAGE} alt="Perkasa Jaya, Dunlop Shop" className="h-24 w-36 max-w-full object-contain lg:hidden" width="144" height="96" />
          <div className="lg:hidden">
            <ThemeToggle compact className="border-[#8295ad] bg-transparent text-[#e2e8f0] hover:bg-[#26374d] hover:text-white focus-visible:ring-[#f1bc3c]" />
          </div>
          <div className="hidden lg:block"><ThemeToggle compact /></div>
        </div>

        <div className="mx-auto w-full max-w-[448px] px-6 pb-12 pt-10 sm:px-8 sm:pt-14 lg:max-w-[432px] lg:px-0 lg:py-20">
          <h1 className="font-heading text-[clamp(1.75rem,2.8vw,2.25rem)] font-semibold leading-tight tracking-tight">Masuk ke aplikasi</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">Gunakan akun admin atau kasir Perkasa Jaya.</p>

          <form
            className="mt-8 space-y-5"
            data-testid="login-form"
            aria-busy={loginMutation.isPending}
            onSubmit={(event) => {
              event.preventDefault();
              loginMutation.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="login-username" className="text-sm font-semibold">Username</Label>
              <Input
                id="login-username"
                data-testid="login-username-input"
                className="min-h-12 px-3 text-base sm:text-sm"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Username akun Anda"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password" className="text-sm font-semibold">Password</Label>
              <div className="relative">
                <Input
                  id="login-password"
                  data-testid="login-password-input"
                  className="min-h-[52px] pl-3 pr-28 text-base sm:text-sm"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Password akun Anda"
                  autoComplete="current-password"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute inset-y-1 right-1 min-h-11 min-w-24 px-2 text-xs text-foreground"
                  data-testid="login-password-visibility"
                  aria-label={showPassword ? "Sembunyikan password" : "Lihat password"}
                  aria-controls="login-password"
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((shown) => !shown)}
                >
                  {showPassword ? "Sembunyikan" : "Lihat"}
                </Button>
              </div>
            </div>

            {loginMutation.isError && (
              <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-3 text-sm leading-5 text-destructive" data-testid="login-error">
                {getApiErrorMessage(loginMutation.error)}
              </p>
            )}

            <Button
              type="submit"
              className="min-h-12 w-full text-sm font-semibold"
              data-testid="login-submit-button"
              disabled={loginMutation.isPending}
            >
              {loginMutation.isPending ? "Sedang masuk..." : "Masuk"}
            </Button>
          </form>

          <p data-testid="login-account-info" className="mt-7 border-t border-border pt-5 text-xs leading-6 text-muted-foreground">Belum punya akun atau lupa password? Hubungi pemilik bengkel untuk mendapatkan akses.</p>
        </div>
      </main>
    </div>
  );
}
