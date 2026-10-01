import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();
  const dark = theme === "dark";
  const label = dark ? "Gunakan mode terang" : "Gunakan mode gelap";
  return <Button type="button" variant="outline" size={compact ? "icon-sm" : "sm"}
    className={compact ? "" : "w-full justify-start"}
    title={label} aria-label={label} aria-pressed={dark} data-testid="theme-toggle"
    onClick={() => setTheme(dark ? "light" : "dark")}>
    {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    {!compact && (dark ? "Mode terang" : "Mode gelap")}
  </Button>;
}
