import { capitalize } from '@/lib/helpers'

interface CategoryBadgeProps {
  category: string
}

export function CategoryBadge({ category }: CategoryBadgeProps) {
  return <span className={`badge badge-${category}`}>{capitalize(category)}</span>
}
