export default function SummaryCard({ label, value }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value ?? 0}</strong>
    </div>
  );
}
