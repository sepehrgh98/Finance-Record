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
  const reviewItems = useMemo(() => buildReviewItems(report), [report]);
  const findingGroups = useMemo(() => groupFindings(reviewItems), [reviewItems]);
  const visibleFindingCount = findingGroups.reduce(
    (total, group) => total + group.items.length,
    0
  );
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
          <li>{visibleFindingCount} things to review surfaced</li>
          <li>{ignoredFiles.length} files ignored</li>
        </ul>
      </section>

      <div className="summary-grid">
        <SummaryCard label="Files Processed" value={metadata.files_processed} />
        <SummaryCard label="Files Ignored" value={metadata.files_ignored} />
        <SummaryCard label="Invoice Count" value={summary.invoice_count} />
        <SummaryCard label="Transaction Count" value={summary.transaction_count} />
        <SummaryCard label="Receipt Count" value={summary.receipt_count} />
        <SummaryCard label="Things to Review" value={visibleFindingCount} />
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
        <h3>Things to Review</h3>
        {visibleFindingCount ? (
          <>
            <div className="finding-category-summary">
              {findingGroups.map((group) => (
                <div className="finding-category-count" key={group.name}>
                  <span>{group.name}</span>
                  <strong>{group.items.length}</strong>
                </div>
              ))}
            </div>
            <div className="finding-groups">
              {findingGroups.filter((group) => group.items.length).map((group) => (
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
                      key={`${finding.finding_type}-${finding.entity_id || finding.synthetic_id || "none"}-${index}`}
                    />
                  ))}
                </div>
              </section>
              ))}
            </div>
          </>
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
  const title = getFindingTitle(finding);
  const description = getFindingDescription(finding);
  const recommendation = getFindingRecommendation(finding);
  const linkedNote = getLinkedNote(finding);
  const matchedTerms = getMatchedTerms(finding);
  const additionalEvidence = getAdditionalEvidence(finding);
  const entityLabel = getEntityLabel(finding);
  const contextItems = [
    entityLabel ? { label: "Entity", value: entityLabel } : null,
    linkedNote ? { label: "Note", value: linkedNote } : null
  ].filter(Boolean);

  return (
    <article
      className={`finding-card finding-${finding.severity || "low"}`}
      key={`${finding.finding_type}-${finding.entity_id || "none"}-${index}`}
    >
      <div className="finding-heading">
        <div>
          <span className="finding-type">{getFindingCategory(finding).name}</span>
          <h4>{title}</h4>
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
      <p className="finding-meaning">{description}</p>
      {contextItems.length ? (
        <dl className="finding-context">
          {contextItems.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="finding-why">{getFindingWhyItMatters(finding)}</p>
      <p className="finding-action">
        <span>Recommended</span>
        {recommendation}
      </p>
      <details className="finding-evidence">
        <summary>Evidence and details</summary>
        <dl>
          {linkedNote ? (
            <>
              <dt>Linked note</dt>
              <dd>{linkedNote}</dd>
            </>
          ) : null}
          {entityLabel ? (
            <>
              <dt>Matched entity</dt>
              <dd>{entityLabel}</dd>
            </>
          ) : null}
          {finding.suggested_action ? (
            <>
              <dt>Original suggested action</dt>
              <dd>{finding.suggested_action}</dd>
            </>
          ) : null}
          <dt>Severity / status</dt>
          <dd>
            {capitalize(finding.severity || "low")} · {capitalize(finding.status || "open")}
          </dd>
          {matchedTerms ? (
            <>
              <dt>Matched terms</dt>
              <dd>{matchedTerms}</dd>
            </>
          ) : null}
        </dl>
        {additionalEvidence.length ? (
          <ul>
            {additionalEvidence.map((item, evidenceIndex) => (
              <li key={`${item}-${evidenceIndex}`}>{item}</li>
            ))}
          </ul>
        ) : null}
        {finding.title || finding.description ? (
          <dl>
            <dt>Source label</dt>
            <dd>{finding.title || formatFindingType(finding.finding_type)}</dd>
            {finding.description ? (
              <>
                <dt>Source description</dt>
                <dd>{finding.description}</dd>
              </>
            ) : null}
          </dl>
        ) : null}
      </details>
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

function buildReviewItems(report) {
  const findings = report.findings || [];
  const linkedNotes = new Set(
    findings.map((finding) => normalizeSearchText(getLinkedNote(finding))).filter(Boolean)
  );
  const items = [...findings];

  (report.action_items || []).forEach((text, index) => {
    const normalized = normalizeSearchText(text);

    if (!normalized || linkedNotes.has(normalized)) {
      return;
    }

    linkedNotes.add(normalized);
    items.push({
      synthetic_id: `action-${index}`,
      finding_type: "action_item",
      group: "Admin",
      severity: inferActionSeverity(text),
      status: "open",
      confidence: "medium",
      title: "Reminder from notes",
      description: text,
      suggested_action: "Add this to your task list.",
      evidence: [`Source note: ${text}`]
    });
  });

  (report.business_rules || []).forEach((text, index) => {
    const normalized = normalizeSearchText(text);

    if (
      !normalized ||
      linkedNotes.has(normalized) ||
      isInternalRecordContext(text)
    ) {
      return;
    }

    items.push({
      synthetic_id: `rule-${index}`,
      finding_type: "record_context",
      group: "Records",
      severity: "low",
      status: "noted",
      confidence: "medium",
      title: "Record-keeping note",
      description: text,
      suggested_action: "Keep this context with the report.",
      evidence: [`Source note: ${text}`]
    });
  });

  (report.annotations || []).forEach((annotation, index) => {
    const note = annotation.note || "";
    const normalized = normalizeSearchText(note);

    if (
      !normalized ||
      linkedNotes.has(normalized) ||
      isInternalRecordContext(note)
    ) {
      return;
    }

    items.push({
      synthetic_id: `annotation-${index}`,
      finding_type: "note_context",
      group: "Records",
      severity: "low",
      status: "noted",
      confidence: "medium",
      title: "Note linked to a record",
      description: note,
      suggested_action: "Keep this note as context.",
      entity_type: annotation.entity_type,
      entity_id: annotation.entity_id,
      entity_name: annotation.entity_name,
      evidence: [`Linked note: ${note}`]
    });
  });

  return items;
}

const REVIEW_CATEGORIES = [
  {
    id: "outstanding_invoices",
    name: "Outstanding Invoices"
  },
  {
    id: "refunds",
    name: "Refunds"
  },
  {
    id: "personal_expense_candidates",
    name: "Personal Expense Candidates"
  },
  {
    id: "missing_documents",
    name: "Missing Documents"
  },
  {
    id: "action_items",
    name: "Action Items / Reminders"
  },
  {
    id: "other",
    name: "Other Review Items"
  }
];

function groupFindings(findings) {
  const groups = REVIEW_CATEGORIES.map((category) => ({
    ...category,
    items: []
  }));
  const byId = new Map(groups.map((group) => [group.id, group]));
  const seen = new Set();

  findings.forEach((finding) => {
    if (!shouldShowFinding(finding)) {
      return;
    }

    const dedupeKey = getFindingDedupeKey(finding);

    if (seen.has(dedupeKey)) {
      return;
    }

    seen.add(dedupeKey);
    const category = getFindingCategory(finding);
    byId.get(category.id)?.items.push(finding);
  });

  return groups;
}

function shouldShowFinding(finding) {
  const type = String(finding.finding_type || "").toLowerCase();

  if (type !== "invoice_follow_up") {
    return true;
  }

  const linkedNote = getLinkedNote(finding);

  if (!linkedNote || !finding.entity_name) {
    return true;
  }

  return noteMentionsEntity(linkedNote, finding.entity_name);
}

function noteMentionsEntity(note, entityName) {
  const noteText = normalizeSearchText(note);
  const entityTokens = normalizeSearchText(entityName)
    .split(" ")
    .filter((token) => token.length >= 4);

  if (!noteText || !entityTokens.length) {
    return true;
  }

  return entityTokens.some((token) => noteText.includes(token));
}

function getFindingDedupeKey(finding) {
  return [
    finding.finding_type || "",
    getFindingCategory(finding).id,
    readableEntityName(finding.entity_name) || finding.entity_id || "",
    getLinkedNote(finding),
    getFindingRecommendation(finding)
  ].join("|").toLowerCase();
}

function getFindingCategory(finding) {
  const type = String(finding.finding_type || "").toLowerCase();
  const group = String(finding.group || "").toLowerCase();

  if (type.includes("invoice") || group.includes("receivable")) {
    return REVIEW_CATEGORIES[0];
  }

  if (type.includes("refund")) {
    return REVIEW_CATEGORIES[1];
  }

  if (type.includes("personal")) {
    return REVIEW_CATEGORIES[2];
  }

  if (isPersonalMoveNote(finding)) {
    return REVIEW_CATEGORIES[2];
  }

  if (
    type.includes("missing") ||
    type.includes("document_availability") ||
    group.includes("missing")
  ) {
    return REVIEW_CATEGORIES[3];
  }

  if (
    type.includes("action") ||
    type.includes("admin") ||
    type.includes("compliance") ||
    type.includes("reminder") ||
    group.includes("admin")
  ) {
    return REVIEW_CATEGORIES[4];
  }

  if (type.includes("record") || type.includes("note_context")) {
    return REVIEW_CATEGORIES[5];
  }

  return REVIEW_CATEGORIES[5];
}

function getFindingTitle(finding) {
  const type = String(finding.finding_type || "").toLowerCase();
  const entity = readableEntityName(finding.entity_name);

  if (type === "invoice_follow_up") {
    return "Outstanding invoice";
  }

  if (type === "refund_context") {
    return entity ? `${entity} refund appears matched` : "Refund appears matched";
  }

  if (type === "possible_personal_expense") {
    return "Possible personal expense";
  }

  if (type.includes("missing")) {
    return "Missing document";
  }

  if (type === "admin_or_compliance_action") {
    return "Reminder or admin task";
  }

  if (type === "action_item") {
    if (isPersonalMoveNote(finding)) {
      return "Possible personal expense";
    }

    return "Reminder from notes";
  }

  if (type === "record_context") {
    return "Record-keeping note";
  }

  if (type === "note_context") {
    return "Note linked to a record";
  }

  if (type === "sales_opportunity") {
    return "Potential client follow-up";
  }

  return finding.title || formatFindingType(type);
}

function getFindingDescription(finding) {
  const type = String(finding.finding_type || "").toLowerCase();
  const entity = readableEntityName(finding.entity_name);

  if (type === "invoice_follow_up") {
    return `${entity || "This client"} appears unpaid based on notes.`;
  }

  if (type === "refund_context") {
    return `A note about ${entity ? `${entity} ` : "a "}refund matches a transaction.`;
  }

  if (type === "possible_personal_expense") {
    return `${entity || "This transaction"} may be a personal purchase based on notes.`;
  }

  if (type.includes("missing")) {
    return `${entity || "A document"} may be missing based on notes.`;
  }

  if (type === "admin_or_compliance_action") {
    return getLinkedNote(finding) || "A note contains a reminder that needs follow-up.";
  }

  if (type === "action_item") {
    if (isPersonalMoveNote(finding)) {
      return "Netflix may belong on a personal card based on notes.";
    }

    return finding.description || getLinkedNote(finding) || "A note contains a reminder.";
  }

  if (type === "record_context") {
    return finding.description || getLinkedNote(finding) || "A note contains record context.";
  }

  if (type === "note_context") {
    return finding.entity_name
      ? `${readableEntityName(finding.entity_name)} has a note attached.`
      : finding.description || "A note is attached to a record.";
  }

  if (type === "sales_opportunity") {
    return `${entity || "A note"} mentions possible future work.`;
  }

  return finding.description || "This item may need review.";
}

function getFindingWhyItMatters(finding) {
  const type = String(finding.finding_type || "").toLowerCase();

  if (type === "invoice_follow_up") {
    return "Why it matters: unpaid invoices affect cash flow.";
  }

  if (type === "refund_context") {
    return "Why it matters: refunds should be kept with the right transaction records.";
  }

  if (type === "possible_personal_expense") {
    return "Why it matters: personal purchases should not stay categorized as business expenses.";
  }

  if (type.includes("missing")) {
    return "Why it matters: missing documents can leave gaps in your records.";
  }

  if (type === "admin_or_compliance_action") {
    return "Why it matters: reminders can turn into deadlines if they are not handled.";
  }

  if (type === "action_item") {
    if (isPersonalMoveNote(finding)) {
      return "Why it matters: personal subscriptions should not stay on a business card.";
    }

    return "Why it matters: this note may require follow-up.";
  }

  if (type === "record_context" || type === "note_context") {
    return "Why it matters: this context can explain how records should be treated.";
  }

  if (type === "sales_opportunity") {
    return "Why it matters: this could be a follow-up opportunity with a client.";
  }

  return "Why it matters: this item may affect your records or follow-up work.";
}

function getFindingRecommendation(finding) {
  const type = String(finding.finding_type || "").toLowerCase();

  if (type === "invoice_follow_up") {
    return "Follow up with the client.";
  }

  if (type === "refund_context") {
    return "Keep this refund for records.";
  }

  if (type === "possible_personal_expense") {
    return "Review and move to personal if confirmed.";
  }

  if (type.includes("missing")) {
    return "Find or request the missing document.";
  }

  if (type === "admin_or_compliance_action") {
    return "Add this to your task list and handle it before the deadline.";
  }

  if (type === "action_item") {
    if (isPersonalMoveNote(finding)) {
      return "Review and move to personal if confirmed.";
    }

    return "Add this to your task list.";
  }

  if (type === "record_context" || type === "note_context") {
    return "Keep this context with the report.";
  }

  if (type === "sales_opportunity") {
    return "Consider adding a client follow-up.";
  }

  return finding.suggested_action || "Review this item.";
}

function getEntityLabel(finding) {
  if (!finding.entity_name) {
    return "";
  }

  return `${finding.entity_name}${finding.entity_type ? ` · ${finding.entity_type}` : ""}`;
}

function getLinkedNote(finding) {
  const evidence = finding.evidence || [];
  const item = evidence.find((entry) =>
    /^(linked note|source note):/i.test(String(entry))
  );

  if (!item) {
    return "";
  }

  return String(item).replace(/^(linked note|source note):\s*/i, "");
}

function getMatchedTerms(finding) {
  const evidence = finding.evidence || [];
  const item = evidence.find((entry) => /^matched terms:/i.test(String(entry)));

  if (!item) {
    return "";
  }

  return String(item).replace(/^matched terms:\s*/i, "");
}

function getAdditionalEvidence(finding) {
  return (finding.evidence || []).filter((entry) => {
    const value = String(entry);
    return !/^(linked note|source note|matched terms):/i.test(value);
  });
}

function inferActionSeverity(text) {
  const normalized = normalizeSearchText(text);

  if (
    normalized.includes("before") ||
    normalized.includes("renew") ||
    normalized.includes("deadline")
  ) {
    return "medium";
  }

  return "low";
}

function isPersonalMoveNote(finding) {
  const text = normalizeSearchText(
    [
      finding.description,
      finding.suggested_action,
      getLinkedNote(finding),
      ...(finding.evidence || [])
    ].join(" ")
  );

  return (
    text.includes("personal") &&
    (text.includes("move") || text.includes("personal card"))
  );
}

function isInternalRecordContext(text) {
  const normalized = normalizeSearchText(text);

  if (
    normalized.includes("receipts of cash purchases") ||
    normalized.includes("receipts folder")
  ) {
    return true;
  }

  if (
    normalized.includes("all sent and paid") ||
    normalized.includes("sent and paid")
  ) {
    return true;
  }

  return false;
}

function readableEntityName(value) {
  const cleaned = String(value || "")
    .replace(/\s+#?\d{3,}\b/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) {
    return "";
  }

  return cleaned
    .toLowerCase()
    .split(" ")
    .map((word) =>
      word.length <= 2 ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1)
    )
    .join(" ")
    .replace(/\bAdobe\b.*$/i, "Adobe")
    .replace(/\bPetco\b.*$/i, "Petco")
    .replace(/\bStaples\b.*$/i, "Staples");
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function capitalize(value) {
  const text = String(value || "");
  return text ? text[0].toUpperCase() + text.slice(1) : "";
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
