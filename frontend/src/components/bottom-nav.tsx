import { motion } from 'motion/react'

import { NAV_ITEMS, type TabKey } from '@/lib/nav'
import { cn } from '@/lib/utils'

export function BottomNav({
  active,
  onChange,
}: {
  active: TabKey
  onChange: (key: TabKey) => void
}) {
  return (
    <nav className="glass-strong relative z-20 border-t border-white/10 pb-safe">
      <ul className="grid grid-cols-4 gap-1 px-2 py-1.5">
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active
          const Icon = item.icon
          return (
            <li key={item.key}>
              <button
                type="button"
                onClick={() => onChange(item.key)}
                aria-current={isActive ? 'page' : undefined}
                className="relative flex w-full select-none flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {isActive && (
                  <motion.span
                    layoutId="bottom-nav-pill"
                    className="absolute inset-0 -z-10 rounded-2xl bg-primary/15 ring-1 ring-primary/25"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                <Icon
                  className={cn(
                    'size-5 transition-colors',
                    isActive ? 'text-primary' : 'text-muted-foreground',
                  )}
                />
                <span
                  className={cn(
                    'text-[0.68rem] font-medium leading-none transition-colors',
                    isActive ? 'text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {item.label}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
