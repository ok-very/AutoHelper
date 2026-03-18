import { ModuleLayout } from '@/components/ModuleLayout';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export function ArtCollectorPage() {
  return (
    <ModuleLayout module="art-collector" activePage="collector">
      <PlaceholderPage
        title="Art Collector"
        description="Collect artist images, bios, and metadata from the web. Supports Cargo, Squarespace, WordPress, and generic sites."
        detail="Backend ready — UI in progress"
      />
    </ModuleLayout>
  );
}
