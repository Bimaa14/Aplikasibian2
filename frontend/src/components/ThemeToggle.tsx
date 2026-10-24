import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function ThemeToggle({ compact = false, className }: { compact?: boolean; className?: string }) {
  const { theme, setTheme } = useTheme();
  const dark = theme === "dark";
  const label = dark ? "Gunakan mode terang" : "Gunakan mode gelap";

  return (
    <Button
      type="button"
      variant="outline"
      size={compact ? "icon" : "sm"}
      className={cn(compact ? "size-11" : "min-h-11 w-full justify-start gap-3 px-3", className)}
      title={label}
      aria-label={label}
      aria-pressed={dark}
      data-testid="theme-toggle"
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun aria-hidden="true" className="size-[18px]" /> : <Moon aria-hidden="true" className="size-[18px]" />}
      {!compact && (dark ? "Mode terang" : "Mode gelap")}
    </Button>
  );
}
