import { ModuleLayout } from '@/components/ModuleLayout'
import { PlaceholderPage } from '@/components/PlaceholderPage'

export function MailPage() {
  return (
    <ModuleLayout module="mail" activePage="inbox">
      <PlaceholderPage
        title="Mail"
        description="Email polling and inbox monitoring."
        detail="Configure mail polling in settings."
      />
    </ModuleLayout>
  )
}
