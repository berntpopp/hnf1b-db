/** Shared, verified cleanup for E2E records. */

const authHeader = (token) => ({ Authorization: `Bearer ${token}` });

async function jsonBody(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function archiveRecord(request, apiBase, adminToken, recordId, recordCreated) {
  const currentResponse = await request.get(`${apiBase}/phenopackets/${recordId}`, {
    headers: authHeader(adminToken),
  });
  const currentBody = await jsonBody(currentResponse);
  if (currentResponse.status() === 404 && !recordCreated) {
    return { archived: false, alreadyArchived: false };
  }
  if (!currentResponse.ok()) {
    throw new Error(
      `load ${recordId} for cleanup: ${currentResponse.status()} ${JSON.stringify(currentBody)}`
    );
  }
  if (currentBody.effective_state === 'archived') {
    return { archived: true, alreadyArchived: true };
  }

  const archiveResponse = await request.post(`${apiBase}/phenopackets/${recordId}/transitions`, {
    headers: authHeader(adminToken),
    data: {
      to_state: 'archived',
      reason: 'Archive completed E2E record',
      revision: currentBody.revision,
    },
  });
  const archiveBody = await jsonBody(archiveResponse);
  if (!archiveResponse.ok()) {
    throw new Error(
      `archive ${recordId}: ${archiveResponse.status()} ${JSON.stringify(archiveBody)}`
    );
  }
  if (archiveBody?.phenopacket?.effective_state !== 'archived') {
    throw new Error(`archive ${recordId}: response did not confirm archived state`);
  }
  return { archived: true, alreadyArchived: false };
}

/**
 * Archive a created test record without replacing a test's primary failure.
 *
 * A missing record is valid only when creation never completed. Every other
 * GET/transition response is checked so cleanup failures cannot be silent.
 */
export async function archiveE2ERecord(
  request,
  apiBase,
  adminToken,
  recordId,
  { recordCreated = false, primaryError = null } = {}
) {
  try {
    return await archiveRecord(request, apiBase, adminToken, recordId, recordCreated);
  } catch (cleanupError) {
    if (!primaryError) throw cleanupError;
    primaryError.cleanupError = cleanupError;
    primaryError.message += `; cleanup failed for ${recordId}: ${cleanupError.message}`;
    return { archived: false, alreadyArchived: false };
  }
}
