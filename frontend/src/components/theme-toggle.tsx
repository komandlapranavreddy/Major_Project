import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Switch } from "@/components/ui/switch";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid a light/dark flash: don't render the real state until hydrated on the client
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <div className="relative flex items-center" aria-label="Toggle theme">
      <Sun className="absolute left-1 h-3.5 w-3.5 text-amber-500 pointer-events-none z-10" />
      <Moon className="absolute right-1 h-3.5 w-3.5 text-indigo-100 pointer-events-none z-10" />
      <Switch
        checked={isDark}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
      />
    </div>
  );
}
