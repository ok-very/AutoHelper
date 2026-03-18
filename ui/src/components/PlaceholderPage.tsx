interface PlaceholderPageProps {
  title: string;
  description: string;
  detail?: string;
}

export function PlaceholderPage({ title, description, detail }: PlaceholderPageProps) {
  return (
    <div className="placeholder-page">
      <h1>{title}</h1>
      <p className="placeholder-desc">{description}</p>
      {detail && <p className="placeholder-detail">{detail}</p>}
      <span className="placeholder-badge">Coming Soon</span>
    </div>
  );
}
