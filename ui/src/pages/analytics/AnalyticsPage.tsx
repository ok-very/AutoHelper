import { ModuleLayout } from '@/components/ModuleLayout';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export function AnalyticsPage() {
  return (
    <ModuleLayout module="analytics" activePage="overview">
      <PlaceholderPage
        title="System Analytics"
        description="Usage metrics, service health, and system overview."
      />
    </ModuleLayout>
  );
}
