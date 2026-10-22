import * as React from 'react'
import { cn } from 'cn'

/** Etiqueta de sección: mayúsculas pequeñas con tracking amplio. */
function Kicker({ className, ...props }: React.ComponentProps<'p'>) {
  return (
    <p
      data-slot="kicker"
      className={cn(
        'text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-muted-foreground',
        className
      )}
      {...props}
    />
  )
}

export { Kicker }
