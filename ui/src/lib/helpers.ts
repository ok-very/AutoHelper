export function capitalize(s: string | null | undefined): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''
}

export function basename(p: string | null | undefined): string {
  return p ? p.split(/[/\\]/).pop() ?? '' : ''
}
