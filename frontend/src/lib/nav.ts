import { Moon, Network, Settings, Sparkles, type LucideIcon } from 'lucide-react'

export type TabKey = 'dreams' | 'graph' | 'patterns' | 'settings'

export interface NavItem {
  key: TabKey
  label: string
  title: string
  subtitle: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { key: 'dreams', label: 'Sueños', title: 'Sueños', subtitle: 'Tu diario onírico', icon: Moon },
  { key: 'graph', label: 'Grafo', title: 'Grafo 3D', subtitle: 'Mapa de conexiones', icon: Network },
  { key: 'patterns', label: 'Patrones', title: 'Patrones', subtitle: 'Lo que se repite', icon: Sparkles },
  { key: 'settings', label: 'Config', title: 'Configuración', subtitle: 'IA y privacidad', icon: Settings },
]

export function navItem(key: TabKey): NavItem {
  return NAV_ITEMS.find((item) => item.key === key) ?? NAV_ITEMS[0]
}
