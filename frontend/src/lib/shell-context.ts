import { createContext, useContext } from 'react'

export interface ShellContextValue {
  /** Nodo del "teléfono": los bottom sheets se montan acá para no salir del marco. */
  container: HTMLElement | null
  /** Capa por encima de todo (FAB, etc.), recortada al teléfono. */
  floating: HTMLElement | null
}

export const ShellContext = createContext<ShellContextValue>({ container: null, floating: null })

export function useShell() {
  return useContext(ShellContext)
}
