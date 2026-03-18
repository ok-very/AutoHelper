import { ModuleLayout } from '@/components/ModuleLayout'
import { PlaceholderPage } from '@/components/PlaceholderPage'

export function ContactsPage() {
  return (
    <ModuleLayout module="contacts" activePage="contacts">
      <PlaceholderPage
        title="Contacts"
        description="Exchange contact management."
        detail="Contact sync configured in settings."
      />
    </ModuleLayout>
  )
}
