import { useMemo, useState } from "react";
import SummaryCard from "../components/SummaryCard.jsx";
import DataTable from "../components/DataTable.jsx";

export default function ReportPage({ entities, report, reportId }) {
  const [revenueView, setRevenueView] = useState("all");
  const [expenseView, setExpenseView] = useState("card");
  const metadata = report.metadata || {};
  const summary = report.summary || {};
  const revenue = report.revenue || {};
  const expenses = report.expenses || {};
  const findings = report.findings || [];
  const findingGroups = useMemo(() => groupFindings(findings), [findings]);
  const ignoredFiles = report.ignored_files || [];
  const invoiceRows = useMemo(() => buildInvoiceRows(entities, revenue), [
    entities,
    revenue
  ]);
  const transactionRows = useMemo(() => buildTransactionRows(entities), [entities]);
  const receiptRows = useMemo(() => buildReceiptRows(entities), [entities]);
  const displayedInvoices = invoiceRows.filter((invoice) => {
    if (revenueView === "paid") {
      return invoice.status.toLowerCase() === "paid";
    }

    if (revenueView === "outstanding") {
      return invoice.status.toLowerCase() === "outstanding";
    }

    return true;
  });
  const displayedExpenses =
    expenseView === "cash"
      ? receiptRows
      : transactionRows.filter((transaction) => {
          if (expenseView === "refunds") {
            return transaction.amount < 0;
          }

          return transaction.amount > 0;
        });

  return (
    <section className="report-panel">
      <div className="report-header">
        <div>
          <h2>Analysis Report</h2>
          <p>
            Report #{reportId} - {formatDateTime(metadata.analysis_date)}
          </p>
        </div>
      </div>

      <section className="analysis-summary">
        <h3>Analysis Summary</h3>
        <ul>
          <li>{countOutstanding(invoiceRows)} outstanding invoices</li>
          <li>{findings.length} findings surfaced</li>
          <li>{ignoredFiles.length} files ignored</li>
        </ul>
      </section>

      <div className="summary-grid">
        <SummaryCard label="Files Processed" value={metadata.files_processed} />
        <SummaryCard label="Files Ignored" value={metadata.files_ignored} />
        <SummaryCard label="Invoice Count" value={summary.invoice_count} />
        <SummaryCard label="Transaction Count" value={summary.transaction_count} />
        <SummaryCard label="Receipt Count" value={summary.receipt_count} />
        <SummaryCard label="Finding Count" value={summary.finding_count} />
      </div>

      <section className="report-section">
        <h3>Revenue</h3>
        <div className="metric-row">
          <Metric
            active={revenueView === "all"}
            label="Total Invoiced"
            onClick={() => setRevenueView("all")}
            value={money(revenue.total_invoiced)}
          />
          <Metric
            active={revenueView === "paid"}
            label="Total Paid"
            onClick={() => setRevenueView("paid")}
            value={money(revenue.total_paid)}
          />
          <Metric
            active={revenueView === "outstanding"}
            label="Total Outstanding"
            onClick={() => setRevenueView("outstanding")}
            value={money(revenue.total_outstanding)}
          />
        </div>
        <DataTable
          columns={[
            {
              key: "client",
              label: "Client",
              render: (value, row) => (
                <span className="client-with-badge">
                  <span>{value}</span>
                  {row.status.toLowerCase() === "outstanding" ? (
                    <span className="status-badge">Outstanding</span>
                  ) : null}
                </span>
              )
            },
            { key: "description", label: "Description" },
            { key: "amount", label: "Amount", format: "currency" },
            { key: "date_sent", label: "Date Sent" },
            { key: "status", label: "Status" }
          ]}
          rows={displayedInvoices}
        />
      </section>

      <section className="report-section">
        <h3>Expenses</h3>
        <div className="metric-row">
          <Metric
            active={expenseView === "card"}
            label="Card Expenses"
            onClick={() => setExpenseView("card")}
            value={money(expenses.total_card_expenses)}
          />
          <Metric
            active={expenseView === "cash"}
            label="Cash Expenses"
            onClick={() => setExpenseView("cash")}
            value={money(expenses.total_cash_expenses)}
          />
          <Metric
            active={expenseView === "refunds"}
            label="Refunds"
            onClick={() => setExpenseView("refunds")}
            value={money(expenses.total_refunds)}
          />
        </div>
        <DataTable
          columns={
            expenseView === "cash"
              ? [
                  { key: "merchant", label: "Merchant" },
                  { key: "total", label: "Amount", format: "currency" },
                  { key: "date", label: "Date" },
                  { key: "payment_method", label: "Payment Method" }
                ]
              : [
                  { key: "vendor", label: "Vendor" },
                  {
                    key: "amount",
                    label: "Amount",
                    render: (value) => money(Math.abs(value))
                  },
                  { key: "date", label: "Date" },
                  { key: "transaction_type", label: "Type" }
                ]
          }
          rows={displayedExpenses}
        />
      </section>

      <section className="report-section">
        <h3>Findings</h3>
        {findings.length ? (
          <div className="finding-groups">
            {findingGroups.map((group) => (
              <section className="finding-group" key={group.name}>
                <div className="finding-group-heading">
                  <h4>{group.name}</h4>
                  <span>{group.items.length}</span>
                </div>
                <div className="finding-list">
                  {group.items.map((finding, index) => (
                    <FindingCard
                      finding={finding}
                      index={index}
                      key={`${finding.finding_type}-${finding.entity_id || "none"}-${index}`}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <p className="empty-state">No items found.</p>
        )}
      </section>

      <section className="report-section">
        <h3>Ignored Files</h3>
        <DataTable
          columns={[
            { key: "filename", label: "Filename" },
            { key: "reason", label: "Reason", className: "muted-cell note-cell" }
          ]}
          rows={ignoredFiles}
        />
      </section>
    </section>
  );
}

function FindingCard({ finding, index }) {
  return (
    <article
      className={`finding-card finding-${finding.severity || "low"}`}
      key={`${finding.finding_type}-${finding.entity_id || "none"}-${index}`}
    >
      <div className="finding-heading">
        <div>
          <span className="finding-type">
            {formatFindingType(finding.finding_type)}
          </span>
          <h4>{finding.title}</h4>
        </div>
        <div className="finding-badges">
          <span className={`status-pill status-${finding.status || "open"}`}>
            {finding.status || "open"}
          </span>
          <span className={`severity-badge severity-${finding.severity || "low"}`}>
            {finding.severity || "low"}
          </span>
        </div>
      </div>
      <p>{finding.description}</p>
      {finding.entity_name ? (
        <p className="finding-entity">
          {finding.entity_name} · {finding.entity_type}
        </p>
      ) : null}
      {finding.suggested_action ? (
        <p className="finding-action">
          Suggested action: {finding.suggested_action}
        </p>
      ) : null}
      {finding.evidence?.length ? (
        <ul>
          {finding.evidence.map((item, evidenceIndex) => (
            <li key={`${item}-${evidenceIndex}`}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function Metric({ active, label, onClick, value }) {
  return (
    <button
      className={`metric metric-button ${active ? "metric-active" : ""}`}
      onClick={onClick}
      type="button"
    >
      <span>{label}</span>
      <strong>{value}</strong>
    </button>
  );
}

function buildInvoiceRows(entities, revenue) {
  const invoiceEntities = entities.filter((entity) => entity.entity_type === "invoice");

  if (invoiceEntities.length) {
    return invoiceEntities.map((entity) => ({
      id: entity.id,
      client: entity.data?.client || entity.entity_name,
      description: entity.data?.description || "",
      amount: Number(entity.data?.amount || 0),
      date_sent: entity.data?.date_sent || "",
      date_paid: entity.data?.date_paid || "",
      status: entity.data?.status || ""
    }));
  }

  return (revenue.outstanding_invoices || []).map((invoice) => ({
    ...invoice,
    status: invoice.status || "outstanding"
  }));
}

function buildTransactionRows(entities) {
  return entities
    .filter((entity) => entity.entity_type === "transaction")
    .map((entity) => ({
      id: entity.id,
      vendor: entity.data?.vendor || entity.entity_name,
      amount: Number(entity.data?.amount || 0),
      date: entity.data?.date || "",
      transaction_type: entity.data?.transaction_type || ""
    }));
}

function buildReceiptRows(entities) {
  return entities
    .filter((entity) => entity.entity_type === "receipt")
    .map((entity) => ({
      id: entity.id,
      merchant: entity.data?.merchant || entity.entity_name,
      total: Number(entity.data?.total || 0),
      date: entity.data?.date || "",
      payment_method: entity.data?.payment_method || ""
    }));
}

function countOutstanding(invoices) {
  return invoices.filter(
    (invoice) => invoice.status.toLowerCase() === "outstanding"
  ).length;
}

function groupFindings(findings) {
  const preferredOrder = [
    "Money to Review",
    "Receivables",
    "Business Development",
    "Admin"
  ];
  const groups = new Map();

  for (const finding of findings) {
    const groupName = finding.group || "Other";

    if (!groups.has(groupName)) {
      groups.set(groupName, []);
    }

    groups.get(groupName).push(finding);
  }

  return [...groups.entries()]
    .sort(([left], [right]) => {
      const leftIndex = preferredOrder.indexOf(left);
      const rightIndex = preferredOrder.indexOf(right);

      if (leftIndex === -1 && rightIndex === -1) {
        return left.localeCompare(right);
      }

      if (leftIndex === -1) {
        return 1;
      }

      if (rightIndex === -1) {
        return -1;
      }

      return leftIndex - rightIndex;
    })
    .map(([name, items]) => ({ name, items }));
}

function money(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(Number(value || 0));
}

function formatFindingType(value) {
  return String(value || "finding")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value) {
  if (!value) {
    return "Analysis date unavailable";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return `Generated ${new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date)}`;
}
