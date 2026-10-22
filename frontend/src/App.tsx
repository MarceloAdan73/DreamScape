import { lazy, Suspense, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'

import { AppBar } from '@/components/app-bar'
import { AppShell } from '@/components/app-shell'
import { BottomNav } from '@/components/bottom-nav'
import { DreamsView } from '@/components/dreams-view'
import { PatternsView } from '@/components/patterns-view'
import { SettingsView } from '@/components/settings-view'
import { Toaster } from '@/components/ui/sonner'
import { navItem, type TabKey } from '@/lib/nav'

const GraphView = lazy(() =>
  import('@/components/graph-view').then((module) => ({ default: module.GraphView }))
)

function CurrentView({ tab }: { tab: TabKey }) {
  switch (tab) {
    case 'graph':
      return (
        <Suspense
          fallback={
            <div className="grid h-full place-items-center bg-[#050816] text-sm text-muted-foreground">
              Cargando grafo…
            </div>
          }
        >
          <GraphView />
        </Suspense>
      )
    case 'patterns':
      return <PatternsView />
    case 'settings':
      return <SettingsView />
    default:
      return <DreamsView />
  }
}

export default function App() {
  const [tab, setTab] = useState<TabKey>('dreams')

  // Cada pestaña es una pantalla nueva: volver siempre arriba.
  useEffect(() => {
    document.querySelector('main')?.scrollTo({ top: 0 })
  }, [tab])

  const fullBleed = tab === 'graph'

  return (
    <>
      <AppShell
        header={<AppBar item={navItem(tab)} />}
        footer={<BottomNav active={tab} onChange={setTab} />}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className={fullBleed ? 'h-full' : 'px-4 py-4 lg:px-8 lg:py-6'}
          >
            <CurrentView tab={tab} />
          </motion.div>
        </AnimatePresence>
      </AppShell>
      <Toaster />
    </>
  )
}
