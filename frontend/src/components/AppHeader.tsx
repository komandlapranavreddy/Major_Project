import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, BarChart3, FlaskConical, History, ScanSearch } from 'lucide-react';
import { Logo } from '@/components/landing/logo';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { easeOut } from '@/lib/design';

const NAV = [
  { to: '/app', label: 'Analyze', icon: ScanSearch },
  { to: '/history', label: 'History', icon: History },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/research', label: 'Research', icon: FlaskConical },
];

export function AppHeader({ center }: { center?: ReactNode }) {
  return (
    <header className="glass-strong sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-4">
        <Link to="/" aria-label="EdgeLegal home">
          <Logo />
        </Link>
        <div className="hidden h-6 w-px bg-border xl:block" />
        <p className="hidden text-xs font-medium uppercase tracking-wide text-muted-foreground xl:block">
          Document Intelligence Pipeline
        </p>
      </div>

      {center}

      <div className="flex items-center gap-2 sm:gap-3">
        <nav aria-label="App sections" className="glass flex items-center gap-0.5 rounded-xl p-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'relative flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-3',
                  isActive ? 'text-white' : 'text-muted-foreground hover:text-foreground'
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="app-nav-active"
                      className="absolute inset-0 rounded-lg bg-gradient-brand shadow-[0_6px_16px_-8px_hsl(var(--primary)/0.8)]"
                      transition={{ duration: 0.35, ease: easeOut }}
                    />
                  )}
                  <Icon className="relative h-4 w-4" />
                  <span className="relative hidden sm:inline">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <ThemeToggle />
        <Button asChild variant="secondary" size="sm" className="hidden px-3 sm:inline-flex">
          <Link to="/" aria-label="Back to site">
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden md:inline">Back to site</span>
          </Link>
        </Button>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"
      />
    </header>
  );
}
