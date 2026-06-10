export default function ListSection({
  title,
  items,
  cardClassName = "note-card"
}) {
  return (
    <section className="report-section">
      <h3>{title}</h3>
      {items.length ? (
        <ul className="card-list">
          {items.map((item, index) => (
            <li className={cardClassName} key={`${item}-${index}`}>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">No items found.</p>
      )}
    </section>
  );
}
