import { GitFork } from "lucide-react";
import { Logo } from "@/components/landing/logo";

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
        <div className="flex items-center gap-2.5">
          <Logo showWordmark={false} markClassName="h-7 w-7" />
          <div>
            <p className="text-sm font-semibold">EdgeLegal</p>
            <p className="text-xs text-muted-foreground">
              Contract contradiction detection with evidence-backed AI reasoning.
            </p>
          </div>
        </div>

        <a
          href="#"
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <GitFork className="h-4 w-4" />
          GitHub
        </a>
      </div>
    </footer>
  );
}
