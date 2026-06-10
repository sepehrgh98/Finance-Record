export async function analyzeFiles(files) {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file, file.webkitRelativePath || file.name);
  });

  const response = await fetch("/analyze", {
    method: "POST",
    body: formData
  });

  const payload = await response.json();

  if (!response.ok || !payload.success) {
    throw new Error(payload.error || "Analysis failed");
  }

  return payload.report_id;
}

export async function getReport(reportId) {
  const response = await fetch(`/reports/${reportId}`);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "Unable to load report");
  }

  return payload;
}

export async function getEntitiesForReport(reportId) {
  const response = await fetch(`/reports/${reportId}/entities`);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "Unable to load entities");
  }

  return payload;
}

export async function getEntity(entityId) {
  const response = await fetch(`/entities/${entityId}`);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "Unable to load entity");
  }

  return payload;
}
