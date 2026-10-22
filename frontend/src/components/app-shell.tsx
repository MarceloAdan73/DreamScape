import { useState, type ReactNode } from 'react'

import { ShellContext } from '@/lib/shell-context'

/**
 * Marco de la app: en móvil ocupa toda la pantalla; en escritorio se muestra
 * como un teléfono centrado sobre un fondo aurora.
 *
 * El `translateZ(0)` crea un containing block para que los `position: fixed`
 * (drawers) queden anclados al teléfono y no a la ventana del navegador.
 */
export function AppShell({
  header,
  footer,
  children,
}: {
  header: ReactNode
  footer: ReactNode
  children: ReactNode
}) {
  const [container, setContainer] = useState<HTMLElement | null>(null)
  const [floating, setFloating] = useState<HTMLElement | null>(null)

  return (
    <ShellContext.Provider value={{ container, floating }}>
      <div className="aurora flex min-h-[100dvh] w-full justify-center sm:items-center sm:p-6">
        <div
          ref={setContainer}
          className="dream-glow relative flex h-[100dvh] w-full max-w-[440px] flex-col overflow-hidden bg-background [transform:translateZ(0)] sm:h-[min(900px,calc(100dvh-3rem))] sm:rounded-[2.5rem] sm:border sm:border-white/10 sm:shadow-2xl sm:shadow-black/60 sm:ring-1 sm:ring-black/40 lg:max-w-[880px] lg:rounded-[2rem]"
        >
          {header}
          <main className="no-scrollbar relative flex-1 overflow-y-auto">{children}</main>
          {footer}
          <div ref={setFloating} className="pointer-events-none absolute inset-0 z-40" />
        </div>
      </div>
    </ShellContext.Provider>
  )
}
