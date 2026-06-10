import { useState } from "react";
import UploadPage from "./pages/UploadPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import {
  getEntitiesForReport,
  getReport
} from "./services/api.js";

export default function App() {
  const [reportId, setReportId] = useState(null);
  const [report, setReport] = useState(null);
  const [entities, setEntities] = useState([]);

  async function handleReportId(nextReportId) {
    setReportId(nextReportId);

    const [nextReport, nextEntities] = await Promise.all([
      getReport(nextReportId),
      getEntitiesForReport(nextReportId)
    ]);

    setReport(nextReport);
    setEntities(nextEntities);
  }

  return (
    <main className="app-shell">
      {report ? (
        <ReportPage
          entities={entities}
          report={report}
          reportId={reportId}
        />
      ) : null}
      <UploadPage onReport={handleReportId} />
    </main>
  );
}
