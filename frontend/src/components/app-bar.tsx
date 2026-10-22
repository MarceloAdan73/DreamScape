import { AnimatePresence, motion } from 'motion/react'
import { MoonStar } from 'lucide-react'

import type { NavItem } from '@/lib/nav'

export function AppBar({ item }: { item: NavItem }) {
  return (
    <header className="glass z-20 border-b border-white/10 pt-safe">
      <div className="flex items-center gap-3 px-4 pb-3 pt-3">
        <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-dream-violet to-dream-pink text-white shadow-lg shadow-dream-violet/30">
          <MoonStar className="size-5" />
        </div>
        <div className="min-w-0 flex-1 overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={item.key}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
            >
              <h1 className="truncate font-display text-lg font-semibold leading-tight tracking-tight">
                {item.title}
              </h1>
              <p className="truncate text-xs text-muted-foreground">{item.subtitle}</p>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </header>
  )
}
