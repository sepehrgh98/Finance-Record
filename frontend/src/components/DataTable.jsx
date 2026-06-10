import { useState } from "react";

export default function DataTable({
  activeRowId = null,
  columns,
  emptyMessage = "No items found.",
  getRowId,
  initialLimit = 10,
  onRowClick,
  rows
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!rows.length) {
    return <p className="empty-state">{emptyMessage}</p>;
  }

  const hasOverflow = rows.length > initialLimit;
  const visibleRows =
    hasOverflow && !isExpanded ? rows.slice(0, initialLimit) : rows;

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => {
              const rowId = getRowId ? getRowId(row) : null;
              const isClickable = Boolean(onRowClick && rowId);
              const isActive = activeRowId && rowId === activeRowId;

              return (
                <tr
                  className={[
                    isClickable ? "clickable-row" : "",
                    isActive ? "active-row" : ""
                  ].join(" ")}
                  key={rowId || index}
                  onClick={() => {
                    if (isClickable) {
                      onRowClick(row, rowId);
                    }
                  }}
                >
                  {columns.map((column) => (
                    <td className={column.className || ""} key={column.key}>
                      {column.render
                        ? column.render(row[column.key], row)
                        : formatValue(row[column.key], column)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {hasOverflow ? (
        <div className="table-footer">
          <span>
            Showing {visibleRows.length} of {rows.length}
          </span>
          <button
            className="table-more-button"
            onClick={() => setIsExpanded((currentValue) => !currentValue)}
            type="button"
          >
            {isExpanded
              ? "Show less"
              : `Show ${rows.length - initialLimit} more`}
          </button>
        </div>
      ) : null}
    </>
  );
}

function formatValue(value, column) {
  if (column.format === "currency") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD"
    }).format(Number(value || 0));
  }

  if (typeof value === "number") {
    return value.toLocaleString(undefined, {
      maximumFractionDigits: 2,
      minimumFractionDigits: value % 1 === 0 ? 0 : 2
    });
  }

  return value || "";
}
