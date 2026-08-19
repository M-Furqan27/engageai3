let orgId = localStorage.getItem('organization_id');
let onboardingState = { services: [], policies: [], documents: [] };
let organizationRecord = null;
let currentWizardStep = 1;
const TOTAL_WIZARD_STEPS = 6;
const WIZARD_STEP_KEY = `engageai_onboarding_step_${localStorage.getItem('user_id') || 'guest'}`;

function persistWizardStep(step = currentWizardStep) {
  const safe = Math.max(1, Math.min(TOTAL_WIZARD_STEPS, Number(step) || 1));
  try { localStorage.setItem(WIZARD_STEP_KEY, String(safe)); } catch (_) { /* storage unavailable */ }
}

function readPersistedWizardStep() {
  try {
    const value = Number(localStorage.getItem(WIZARD_STEP_KEY));
    if (Number.isInteger(value) && value >= 1 && value <= TOTAL_WIZARD_STEPS) return value;
  } catch (_) { /* storage unavailable */ }
  return null;
}

function clearPersistedWizardStep() {
  try { localStorage.removeItem(WIZARD_STEP_KEY); } catch (_) { /* storage unavailable */ }
}

const WIZARD_META = {
  1: { title: 'Organization information', message: 'Start with the business identity your AI assistant will represent.', hint: 'Save organization information to continue.' },
  2: { title: 'Services & packages', message: 'Services are required. Add at least one service manually or by structured document parsing.', hint: 'Required: add at least one saved service to continue to Policies.' },
  3: { title: 'Business policies', message: 'Policies are required. Add at least one customer-facing business policy.', hint: 'Required: add at least one saved policy to continue to FAQs.' },
  4: { title: 'FAQs', message: 'FAQs are optional. Add common customer questions and answers, or continue without adding any.', hint: 'Optional: add FAQs now, or continue.' },
  5: { title: 'Landing Page', message: 'Landing page is optional. Preview your business page or continue.', hint: 'Optional: preview your landing page or continue to activation.' },
  6: { title: 'Ready to activate?', message: 'Review your setup summary before opening the business workspace.', hint: 'Organization, services and policies are complete. FAQs and landing page are optional.' },
};

function firstIncompleteRequiredStep() {
  if (!orgId) return 1;
  if (onboardingState.services.length === 0) return 2;
  if (onboardingState.policies.length === 0) return 3;
  return 6;
}

function currentStepRequirementMet() {
  if (currentWizardStep === 2) return onboardingState.services.length > 0;
  if (currentWizardStep === 3) return onboardingState.policies.length > 0;
  return true;
}

function showInlineNote(selector, message, type = 'success') {
  const el = document.querySelector(selector);
  if (!el) return;
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-exclamation-octagon-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
  el.className = `inline-note compact-note show ${type}`;
  el.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${EngageAI.escapeHtml(message)}</span>`;
}

function setWizardMessage(message, type = 'info') {
  const el = document.getElementById('wizardStepMessage');
  if (!el) return;
  const icons = { success: 'bi-check-circle-fill', warning: 'bi-exclamation-triangle-fill', danger: 'bi-exclamation-octagon-fill', info: 'bi-info-circle' };
  el.className = `wizard-message ${type}`;
  el.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${EngageAI.escapeHtml(message)}</span>`;
}

function fillOrganizationForm(org) {
  const form = document.getElementById('orgForm');
  if (!form || !org) return;
  form.organization_name.value = org.organization_name || '';
  form.organization_type.value = org.organization_type || '';
  form.short_description.value = org.short_description || '';
}

function updateWizardChrome() {
  const meta = WIZARD_META[currentWizardStep];
  document.getElementById('wizardTitle').textContent = meta.title;
  document.getElementById('wizardStepNumber').textContent = currentWizardStep;
  document.getElementById('wizardProgressBar').style.width = `${(currentWizardStep / TOTAL_WIZARD_STEPS) * 100}%`;
  document.getElementById('wizardFooterHint').textContent = meta.hint;

  document.querySelectorAll('.wizard-panel').forEach(panel => {
    panel.classList.toggle('d-none', Number(panel.dataset.panel) !== currentWizardStep);
  });
  document.querySelectorAll('.wizard-step').forEach(step => {
    const n = Number(step.dataset.step);
    step.classList.toggle('active', n === currentWizardStep);
    step.classList.toggle('complete', n < currentWizardStep || (n === 1 && Boolean(orgId)));
    step.disabled = n > currentWizardStep;
  });

  const back = document.getElementById('wizardBackBtn');
  const next = document.getElementById('wizardNextBtn');
  const complete = document.getElementById('completeBtn');
  back.classList.toggle('invisible', currentWizardStep === 1);
  next.classList.toggle('d-none', currentWizardStep === 1 || currentWizardStep === 6);
  complete.classList.toggle('d-none', currentWizardStep !== 6);

  const requirementMet = currentStepRequirementMet();
  next.disabled = currentWizardStep >= 2 && currentWizardStep <= 3 && !requirementMet;
  next.title = next.disabled ? 'Complete this required step before continuing.' : '';

  const allRequiredDataPresent = firstIncompleteRequiredStep() === 6;
  complete.disabled = currentWizardStep === 6 && !allRequiredDataPresent;
  complete.title = complete.disabled ? 'Services and policies are required before activation.' : '';

  setWizardMessage(meta.message, 'info');
  updateFinalSummary();
}

function showWizardStep(step, { announce = true } = {}) {
  const safe = Math.max(1, Math.min(TOTAL_WIZARD_STEPS, Number(step) || 1));
  currentWizardStep = safe;
  persistWizardStep(safe);
  updateWizardChrome();
  if (announce && safe > 1) {
    const names = { 1: 'Organization', 2: 'Services & packages', 3: 'Business policies', 4: 'FAQs', 5: 'landing page', 6: 'Activation review' };
    setWizardMessage(`${names[safe]} step is ready. Your previously saved data is still available.`, 'info');
  }
}

async function previousWizardStep() {
  if (currentWizardStep <= 1) return;
  showWizardStep(currentWizardStep - 1, { announce: false });
  const names = { 1: 'organization information', 2: 'services', 3: 'policies', 4: 'FAQs' };
  setWizardMessage(`Back to ${names[currentWizardStep]}. Make any changes you need, then continue.`, 'info');
}

async function canLeaveCurrentStep() {
  let missingLabel = '';
  if (currentWizardStep === 2 && onboardingState.services.length === 0) missingLabel = 'service';
  if (currentWizardStep === 3 && onboardingState.policies.length === 0) missingLabel = 'policy';
  if (!missingLabel) return true;

  const message = `This step is required. Add at least one ${missingLabel} before continuing.`;
  setWizardMessage(message, 'warning');
  EngageAI.toast(message, 'warning');
  return false;
}

async function nextWizardStep() {
  if (currentWizardStep === 1) return EngageAI.toast('Save organization information to continue.', 'warning');
  if (currentWizardStep >= TOTAL_WIZARD_STEPS) return;
  if (!(await canLeaveCurrentStep())) return;
  const from = currentWizardStep;
  showWizardStep(currentWizardStep + 1, { announce: false });
  const messages = {
    2: 'Services step complete. Next, add your business policies.',
    3: 'Policies step complete. FAQs are optional — add them now or continue.',
    4: 'Knowledge step complete. Landing page is optional — create it now or continue.',
    5: 'Landing page is ready. Review your setup before activation.'
  };
  setWizardMessage(messages[from] || WIZARD_META[currentWizardStep].message, 'success');
}

async function saveOrg(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('saveOrgBtn');
  const payload = Object.fromEntries(new FormData(form));
  EngageAI.setBusy(button, true, orgId ? 'Saving changes...' : 'Creating organization...');
  try {
    let data;
    if (orgId) {
      data = await EngageAI.request(`/organizations/${orgId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      data = await EngageAI.request('/organizations', {
        method: 'POST',
        body: JSON.stringify({ ...payload, user_id: localStorage.getItem('user_id') }),
      });
      orgId = data.organization_id;
      localStorage.setItem('organization_id', orgId);
    }
    organizationRecord = data;
    EngageAI.clearFormDraft('organization');
    fillOrganizationForm(data);
    await refreshAll();
    EngageAI.toast('Organization information saved to Business Profile.', 'success');
    showWizardStep(2, { announce: false });
    setWizardMessage('Organization saved successfully. Now add your services by document or manual entry.', 'success');
  } catch (error) {
    setWizardMessage(error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally {
    EngageAI.setBusy(button, false);
  }
}

function resetServiceForm() {
  const form = document.getElementById('serviceForm');
  form.reset();
  form.elements.service_id.value = '';
  document.getElementById('addServiceBtn').innerHTML = '<i class="bi bi-plus-circle me-2"></i>Add Service';
  document.getElementById('cancelServiceEditBtn').classList.add('d-none');
}

function editServiceOnboarding(serviceId) {
  const service = onboardingState.services.find(item => String(item.service_id) === String(serviceId));
  if (!service) return;
  const form = document.getElementById('serviceForm');
  form.elements.service_id.value = service.service_id;
  form.elements.service_name.value = service.service_name || '';
  form.elements.sub_service_name.value = service.sub_service_name || '';
  form.elements.service_description.value = service.service_description || '';
  form.elements.service_price.value = service.service_price ?? '';
  form.elements.service_requirements.value = service.service_requirements || '';
  document.getElementById('addServiceBtn').innerHTML = '<i class="bi bi-check2-circle me-2"></i>Save Changes';
  document.getElementById('cancelServiceEditBtn').classList.remove('d-none');
  setWizardMessage(`Editing ${service.service_name}. Save the changes when ready.`, 'info');
}

function cancelServiceEdit() {
  resetServiceForm();
  setWizardMessage('Service edit cancelled. Your saved service was not changed.', 'info');
}

async function addService(event) {
  event.preventDefault();
  if (!orgId) return EngageAI.toast('Save organization information first.', 'warning');
  const form = event.currentTarget;
  const button = document.getElementById('addServiceBtn');
  const payload = Object.fromEntries(new FormData(form));
  const serviceId = payload.service_id || '';
  delete payload.service_id;
  payload.service_price = payload.service_price || null;
  EngageAI.setBusy(button, true, serviceId ? 'Saving changes...' : 'Adding service...');
  try {
    if (serviceId) {
      await EngageAI.request(`/services/${serviceId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      payload.organization_id = orgId;
      await EngageAI.request('/services', { method: 'POST', body: JSON.stringify(payload) });
    }
    resetServiceForm();
    EngageAI.clearFormDraft('service');
    await refreshAll();
    const msg = serviceId ? 'Service updated successfully.' : 'Service added successfully. Add another or continue to Policies.';
    showInlineNote('#serviceNote', msg, 'success');
    setWizardMessage(msg, 'success');
    EngageAI.toast(serviceId ? 'Service changes saved.' : 'Service saved to your catalogue.', 'success');
  } catch (error) {
    showInlineNote('#serviceNote', error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally {
    EngageAI.setBusy(button, false);
  }
}

async function deleteServiceOnboarding(serviceId, serviceName) {
  const ok = await EngageAI.confirmAction({ title: 'Delete service?', message: `${serviceName} will be removed from this business.`, confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/services/${serviceId}`, { method: 'DELETE' });
    await refreshAll();
    setWizardMessage(`${serviceName} was deleted.`, 'success');
    EngageAI.toast('Service deleted successfully.', 'success');
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

function resetPolicyForm() {
  const form = document.getElementById('policyForm');
  form.reset();
  form.elements.policy_id.value = '';
  document.getElementById('addPolicyBtn').innerHTML = '<i class="bi bi-plus-circle me-2"></i>Add Policy';
  document.getElementById('cancelPolicyEditBtn').classList.add('d-none');
  refreshServiceOptions();
}

function editPolicyOnboarding(policyId) {
  const policy = onboardingState.policies.find(item => String(item.policy_id) === String(policyId));
  if (!policy) return;
  const form = document.getElementById('policyForm');
  form.elements.policy_id.value = policy.policy_id;
  form.elements.policy_name.value = policy.policy_name || '';
  form.elements.policy_description.value = policy.policy_description || '';
  form.elements.related_service_id.value = policy.related_service_id || '';
  document.getElementById('addPolicyBtn').innerHTML = '<i class="bi bi-check2-circle me-2"></i>Save Changes';
  document.getElementById('cancelPolicyEditBtn').classList.remove('d-none');
  setWizardMessage(`Editing ${policy.policy_name}. Save the changes when ready.`, 'info');
}

function cancelPolicyEdit() {
  resetPolicyForm();
  setWizardMessage('Policy edit cancelled. Your saved policy was not changed.', 'info');
}

async function addPolicy(event) {
  event.preventDefault();
  if (!orgId) return EngageAI.toast('Save organization information first.', 'warning');
  const form = event.currentTarget;
  const button = document.getElementById('addPolicyBtn');
  const payload = Object.fromEntries(new FormData(form));
  const policyId = payload.policy_id || '';
  delete payload.policy_id;
  payload.related_service_id = payload.related_service_id || null;
  EngageAI.setBusy(button, true, policyId ? 'Saving changes...' : 'Adding policy...');
  try {
    if (policyId) {
      await EngageAI.request(`/policies/${policyId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      payload.organization_id = orgId;
      await EngageAI.request('/policies', { method: 'POST', body: JSON.stringify(payload) });
    }
    resetPolicyForm();
    EngageAI.clearFormDraft('policy');
    await refreshAll();
    const msg = policyId ? 'Policy updated successfully.' : 'Policy added successfully. Add another or continue to optional FAQs.';
    showInlineNote('#policyNote', msg, 'success');
    setWizardMessage(msg, 'success');
    EngageAI.toast(policyId ? 'Policy changes saved.' : 'Policy saved successfully.', 'success');
  } catch (error) {
    showInlineNote('#policyNote', error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally {
    EngageAI.setBusy(button, false);
  }
}

async function deletePolicyOnboarding(policyId, policyName) {
  const ok = await EngageAI.confirmAction({ title: 'Delete policy?', message: `${policyName} will be removed from this business.`, confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/policies/${policyId}`, { method: 'DELETE' });
    await refreshAll();
    setWizardMessage(`${policyName} was deleted.`, 'success');
    EngageAI.toast('Policy deleted successfully.', 'success');
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

async function archiveSourceDocument(file, documentType) {
  const body = new FormData();
  body.append('organization_id', orgId);
  body.append('document_type', documentType);
  body.append('file', file, file.name);
  return EngageAI.request('/knowledge-documents', { method: 'POST', body });
}

async function extractFile(kind, inputSelector, noteSelector, button) {
  const input = document.querySelector(inputSelector);
  const file = input?.files?.[0];
  if (!file) return EngageAI.toast('Choose a document first.', 'warning');
  if (!orgId) return EngageAI.toast('Save organization information first.', 'warning');
  const singular = kind === 'services' ? 'service' : 'policy';
  EngageAI.setBusy(button, true, `Reading ${singular} document...`);
  try {
    const body = new FormData();
    body.append('organization_id', orgId);
    body.append('file', file, file.name);
    const data = await EngageAI.request(`/${kind}/extract`, { method: 'POST', body });
    const count = data.count ?? (data[kind] || []).length;

    let archived = true;
    try { await archiveSourceDocument(file, singular); }
    catch (archiveError) { archived = false; console.warn('Source document archive failed:', archiveError); }

    input.value = '';
    const noun = count === 1 ? singular : `${singular}s`;
    const next = kind === 'services' ? 'You can add another service or continue to Policies.' : 'You can add another policy or continue to optional FAQs.';
    const archiveCopy = archived ? ' Source document archived for AI search.' : '';
    const message = `${count} ${noun} added successfully.${archiveCopy} ${next}`;
    showInlineNote(noteSelector, message, 'success');
    setWizardMessage(message, 'success');
    EngageAI.toast(`${count} ${noun} parsed from ${file.name}.`, 'success');
    await refreshAll();
  } catch (error) {
    showInlineNote(noteSelector, `${error.message} Try another document or use manual entry.`, 'danger');
    setWizardMessage(error.message, 'danger');
    EngageAI.toast(error.message, 'danger', 'Document could not be processed');
  } finally { EngageAI.setBusy(button, false); }
}

async function uploadKnowledge(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('knowledgeUploadBtn');
  const file = form.elements.file.files[0];
  if (!file) return EngageAI.toast('Choose an FAQ document first.', 'warning');
  EngageAI.setBusy(button, true, 'Uploading & indexing...');
  try {
    const body = new FormData();
    body.append('organization_id', orgId);
    body.append('document_type', 'general');
    body.append('file', file, file.name);
    await EngageAI.request('/knowledge-documents', { method: 'POST', body });
    form.reset();
    await refreshAll();
    const message = `${file.name} uploaded and indexed successfully. You can add another source or continue.`;
    showInlineNote('#knowledgeNote', message, 'success');
    setWizardMessage(message, 'success');
    EngageAI.toast('FAQ document uploaded and indexed.', 'success');
  } catch (error) {
    showInlineNote('#knowledgeNote', error.message, 'danger');
    setWizardMessage(error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally { EngageAI.setBusy(button, false); }
}

async function addManualKnowledge(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('knowledgeManualBtn');
  const payload = Object.fromEntries(new FormData(form));
  EngageAI.setBusy(button, true, 'Saving FAQ...');
  try {
    await EngageAI.request('/knowledge-documents/manual', { method: 'POST', body: JSON.stringify({ organization_id: orgId, ...payload }) });
    form.reset();
    EngageAI.clearFormDraft('knowledge');
    await refreshAll();
    const message = 'FAQ saved and indexed. Add another FAQ or continue to activation review.';
    showInlineNote('#knowledgeNote', message, 'success');
    setWizardMessage(message, 'success');
    EngageAI.toast('FAQ saved and indexed.', 'success');
  } catch (error) {
    showInlineNote('#knowledgeNote', error.message, 'danger');
    setWizardMessage(error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally { EngageAI.setBusy(button, false); }
}

async function deleteKnowledgeOnboarding(documentId, fileName) {
  const ok = await EngageAI.confirmAction({ title: 'Delete FAQ source?', message: `${fileName} will be removed from FAQs and the search index.`, confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/knowledge-documents/${documentId}`, { method: 'DELETE' });
    await refreshAll();
    setWizardMessage(`${fileName} was removed from FAQs.`, 'success');
    EngageAI.toast('FAQ source deleted successfully.', 'success');
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

async function refreshServiceOptions() {
  if (!orgId) return;
  const services = onboardingState.services.length ? onboardingState.services : await EngageAI.request(`/services/${orgId}`);
  const select = document.querySelector('#policyForm [name=related_service_id]');
  if (!select) return;
  const current = select.value;
  select.innerHTML = '<option value="">General / No related service</option>' + services.map(service =>
    `<option value="${EngageAI.escapeHtml(service.service_id)}">${EngageAI.escapeHtml(service.service_name)}${service.sub_service_name ? ` / ${EngageAI.escapeHtml(service.sub_service_name)}` : ''}</option>`
  ).join('');
  if ([...select.options].some(option => option.value === current)) select.value = current;
}

function renderSavedLists() {
  const serviceHost = document.getElementById('serviceSavedList');
  const policyHost = document.getElementById('policySavedList');
  const knowledgeHost = document.getElementById('knowledgeSavedList');

  if (serviceHost) {
    serviceHost.innerHTML = onboardingState.services.length ? onboardingState.services.map(service => `
      <span class="saved-mini-item">
        <b>${EngageAI.escapeHtml(service.service_name)}</b>
        <button type="button" title="Edit" onclick="editServiceOnboarding('${service.service_id}')"><i class="bi bi-pencil"></i></button>
        <button type="button" class="danger" title="Delete" onclick="deleteServiceOnboarding('${service.service_id}',decodeURIComponent('${encodeURIComponent(service.service_name)}'))"><i class="bi bi-trash3"></i></button>
      </span>`).join('') : '<span class="empty-mini">No services added yet.</span>';
  }

  if (policyHost) {
    policyHost.innerHTML = onboardingState.policies.length ? onboardingState.policies.map(policy => `
      <span class="saved-mini-item">
        <b>${EngageAI.escapeHtml(policy.policy_name)}</b>
        <button type="button" title="Edit" onclick="editPolicyOnboarding('${policy.policy_id}')"><i class="bi bi-pencil"></i></button>
        <button type="button" class="danger" title="Delete" onclick="deletePolicyOnboarding('${policy.policy_id}',decodeURIComponent('${encodeURIComponent(policy.policy_name)}'))"><i class="bi bi-trash3"></i></button>
      </span>`).join('') : '<span class="empty-mini">No policies added yet.</span>';
  }

  const generalDocs = onboardingState.documents.filter(doc => doc.document_type === 'general');
  if (knowledgeHost) {
    knowledgeHost.innerHTML = generalDocs.length ? generalDocs.map(doc => `
      <span class="saved-mini-item">
        <b>${EngageAI.escapeHtml(doc.file_name)}</b>
        <button type="button" class="danger" title="Delete" onclick="deleteKnowledgeOnboarding('${doc.document_id}',decodeURIComponent('${encodeURIComponent(doc.file_name)}'))"><i class="bi bi-trash3"></i></button>
      </span>`).join('') : '<span class="empty-mini">No FAQs added yet.</span>';
  }
}

function updateFinalSummary() {
  const generalDocs = onboardingState.documents.filter(doc => doc.document_type === 'general');
  const orgName = document.getElementById('finalOrgName');
  if (orgName) orgName.textContent = organizationRecord?.organization_name || 'Saved';
  const service = document.getElementById('finalServiceCount'); if (service) service.textContent = onboardingState.services.length;
  const policy = document.getElementById('finalPolicyCount'); if (policy) policy.textContent = onboardingState.policies.length;
  const knowledge = document.getElementById('finalKnowledgeCount'); if (knowledge) knowledge.textContent = generalDocs.length;
}

function updateCounts() {
  const generalDocs = onboardingState.documents.filter(doc => doc.document_type === 'general').length;
  const service = document.getElementById('serviceCount'); if (service) service.textContent = onboardingState.services.length;
  const policy = document.getElementById('policyCount'); if (policy) policy.textContent = onboardingState.policies.length;
  const knowledge = document.getElementById('knowledgeCount'); if (knowledge) knowledge.textContent = generalDocs;
  renderSavedLists();
  updateFinalSummary();
  updateWizardChrome();
}

async function refreshAll() {
  if (!orgId) { updateCounts(); return; }
  try {
    const [services, policies, documents] = await Promise.all([
      EngageAI.request(`/services/${orgId}`),
      EngageAI.request(`/policies/${orgId}`),
      EngageAI.request(`/knowledge-documents/${orgId}`),
    ]);
    onboardingState = { services, policies, documents };
    await refreshServiceOptions();
    updateCounts();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

async function completeOnboarding(button) {
  if (!orgId) return EngageAI.toast('Save organization information before completing onboarding.', 'warning');

  const requiredStep = firstIncompleteRequiredStep();
  if (requiredStep < 6) {
    const labels = { 2: 'at least one service', 3: 'at least one policy' };
    showWizardStep(requiredStep, { announce: false });
    const message = `Onboarding cannot be activated yet. Add ${labels[requiredStep]} to continue.`;
    setWizardMessage(message, 'warning');
    EngageAI.toast(message, 'warning');
    return;
  }

  EngageAI.setBusy(button, true, 'Activating workspace...');
  try {
    await EngageAI.request(`/organizations/${orgId}/complete-onboarding`, {
      method: 'POST',
      body: JSON.stringify({ user_id: localStorage.getItem('user_id') }),
    });
    localStorage.setItem('onboarding_completed', 'true');
    clearPersistedWizardStep();
    EngageAI.flash('Onboarding completed. Your EngageAI workspace is ready.', 'success');
    location.href = 'dashboard.html';
  } catch (error) {
    setWizardMessage(error.message, 'danger');
    EngageAI.toast(error.message, 'danger');
  } finally { EngageAI.setBusy(button, false); }
}

document.addEventListener('DOMContentLoaded', async () => {
  if (!EngageAI.requireAuth({ allowIncomplete: true })) return;
  if (localStorage.getItem('onboarding_completed') === 'true') {
    location.href = 'dashboard.html';
    return;
  }
  EngageAI.renderHeader({ onboarding: true });

  EngageAI.bindDraft(document.getElementById('orgForm'), 'organization');
  EngageAI.bindDraft(document.getElementById('serviceForm'), 'service');
  EngageAI.bindDraft(document.getElementById('policyForm'), 'policy');
  EngageAI.bindDraft(document.getElementById('knowledgeManualForm'), 'knowledge');

  if (orgId) {
    try {
      organizationRecord = await EngageAI.request(`/organizations/${orgId}`);
      fillOrganizationForm(organizationRecord);
      EngageAI.clearFormDraft('organization');
    } catch (error) {
      EngageAI.toast(error.message, 'danger');
    }
  }

  await refreshAll();
  await refreshServiceOptions();

  // Resume exactly where the owner was working. This also survives Live Server
  // reloads triggered when uploaded files are written inside the project folder.
  // For older sessions without a saved wizard step, a saved organization resumes at Services.
  const persistedStep = readPersistedWizardStep();
  if (!orgId) {
    currentWizardStep = 1;
  } else {
    const requestedStep = persistedStep || 2;
    const requiredGateStep = firstIncompleteRequiredStep();
    currentWizardStep = Math.min(requestedStep, requiredGateStep);
  }
  persistWizardStep(currentWizardStep);
  updateWizardChrome();

  document.querySelectorAll('.wizard-step').forEach(step => {
    step.addEventListener('click', () => {
      const target = Number(step.dataset.step);
      if (target <= currentWizardStep) showWizardStep(target);
    });
  });

  const modalEl = document.getElementById('onboardingWizardModal');
  const bootScreen = document.getElementById('onboardingBootScreen');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: 'static', keyboard: false });
  modalEl.addEventListener('shown.bs.modal', () => {
    if (bootScreen) bootScreen.classList.add('hidden');
  }, { once: true });
  modal.show();

  // Keep the exact current step even if the page is refreshed by the dev server.
  window.addEventListener('pagehide', () => persistWizardStep(currentWizardStep));
});

function previewLandingPage() {
  const organizationId = localStorage.getItem('organization_id');

  if (!organizationId) {
    return EngageAI.toast(
      'Organization information must be saved first.',
      'warning'
    );
  }

  window.open(
    `./landing-page.html?organization_id=${organizationId}`,
    '_blank'
  );
}

async function enableLandingPage() {
  if (!orgId) {
    return EngageAI.toast('Save organization information first.', 'warning');
  }

  try {
    await EngageAI.request(`/organizations/${orgId}`, {
      method: 'PUT',
      body: JSON.stringify({
        landing_page_enabled: true
      })
    });

    EngageAI.toast('Landing page published successfully.', 'success');
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}