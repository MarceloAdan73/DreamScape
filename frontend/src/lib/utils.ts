export { cn } from "cn"

const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** Fecha del sueño como "12 oct 2026": usa `dreamed_at` y cae a `created_at`. */
export function formatDreamDate(dreamedAt: string | null, createdAt: string): string {
  if (dreamedAt) {
    const [year, month, day] = dreamedAt.split('-').map(Number)
    if (year && month && day) {
      return `${day} ${MONTHS_ES[month - 1]} ${year}`
    }
  }
  const created = new Date(createdAt)
  return `${created.getDate()} ${MONTHS_ES[created.getMonth()]} ${created.getFullYear()}`
}
