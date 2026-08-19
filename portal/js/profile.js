const orgId = localStorage.getItem('organization_id');
let profileData = { organization: null, services: [], policies: [], documents: [] };
let editorParent = null;

function modal(id) { return bootstrap.Modal.getOrCreateInstance(document.getElementById(id)); }

function formatServicePrice(value) {
  if (value === null || value === undefined || value === '') return 'Not set';
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value);
}

function compactPreview(items, getLabel, emptyText) {
  if (!items.length) return emptyText;
  const labels = items.slice(0, 2).map(getLabel).filter(Boolean);
  const remaining = items.length - labels.length;
  return `${labels.join(' • ')}${remaining > 0 ? ` • +${remaining} more` : ''}`;
}

function openManager(id) {
  modal(id).show();
}

function openChildEditor(parentId, childId) {
  const parentElement = document.getElementById(parentId);
  editorParent = { parentId, childId };

  if (parentElement.classList.contains('show')) {
    parentElement.addEventListener('hidden.bs.modal', () => modal(childId).show(), { once: true });
    modal(parentId).hide();
  } else {
    modal(childId).show();
  }
}

function openServicesManager() { renderServices(); openManager('servicesManagerModal'); }
function openPoliciesManager() { renderPolicies(); openManager('policiesManagerModal'); }
function openKnowledgeManager() { renderDocuments(); openManager('knowledgeManagerModal'); }

function renderServices() {
  const container = document.getElementById('services');
  document.getElementById('servicesCount').textContent = profileData.services.length;
  document.getElementById('servicesManagerCount').textContent = profileData.services.length;
  document.getElementById('servicesPreview').textContent = compactPreview(
    profileData.services,
    service => service.service_name,
    'No services added yet. Open this section to add your first service.'
  );
  if (!profileData.services.length) {
    container.innerHTML = '<div class="empty-state"><i class="bi bi-grid"></i>No services yet. Add your first service.</div>';
    return;
  }
  container.innerHTML = profileData.services.map(service => `
    <div class="catalogue-item">
      <div class="d-flex align-items-start justify-content-between gap-2">
        <div class="min-w-0"><div class="catalogue-title">${EngageAI.escapeHtml(service.service_name)}${service.sub_service_name ? ` <span class="text-secondary fw-normal">/ ${EngageAI.escapeHtml(service.sub_service_name)}</span>` : ''}</div>
        <div class="catalogue-meta">${EngageAI.escapeHtml(service.service_description || '')}</div></div>
        <span class="service-price-chip ${service.service_price == null || service.service_price === '' ? 'is-empty' : ''}"><small>Price</small><strong>${EngageAI.escapeHtml(formatServicePrice(service.service_price))}</strong></span>
      </div>
      <div class="catalogue-meta mt-2"><i class="bi bi-list-check me-1"></i>${EngageAI.escapeHtml(service.service_requirements || 'No requirements specified')}</div>
      <div class="catalogue-actions">
        <button class="btn btn-soft btn-sm" type="button" onclick="editService('${service.service_id}')"><i class="bi bi-pencil me-1"></i>Edit</button>
        <button class="btn btn-soft btn-sm text-danger" type="button" onclick="deleteService('${service.service_id}')"><i class="bi bi-trash3 me-1"></i>Delete</button>
      </div>
    </div>`).join('');
}

function renderPolicies() {
  const container = document.getElementById('policies');
  document.getElementById('policiesCount').textContent = profileData.policies.length;
  document.getElementById('policiesManagerCount').textContent = profileData.policies.length;
  document.getElementById('policiesPreview').textContent = compactPreview(
    profileData.policies,
    policy => policy.policy_name,
    'No policies added yet. Open this section to add your business rules.'
  );
  if (!profileData.policies.length) {
    container.innerHTML = '<div class="empty-state"><i class="bi bi-shield-check"></i>No policies yet. Add your business rules.</div>';
    return;
  }
  const serviceMap = Object.fromEntries(profileData.services.map(service => [service.service_id, service.service_name]));
  container.innerHTML = profileData.policies.map(policy => `
    <div class="catalogue-item">
      <div class="d-flex align-items-start justify-content-between gap-2">
        <div><div class="catalogue-title">${EngageAI.escapeHtml(policy.policy_name)}</div><div class="catalogue-meta">${EngageAI.escapeHtml(policy.policy_description || '')}</div></div>
        <span class="count-chip">${EngageAI.escapeHtml(serviceMap[policy.related_service_id] || 'General')}</span>
      </div>
      <div class="catalogue-actions">
        <button class="btn btn-soft btn-sm" type="button" onclick="editPolicy('${policy.policy_id}')"><i class="bi bi-pencil me-1"></i>Edit</button>
        <button class="btn btn-soft btn-sm text-danger" type="button" onclick="deletePolicy('${policy.policy_id}')"><i class="bi bi-trash3 me-1"></i>Delete</button>
      </div>
    </div>`).join('');
}

function renderDocuments() {
  const container = document.getElementById('docs');
  document.getElementById('docsCount').textContent = profileData.documents.length;
  document.getElementById('docsManagerCount').textContent = profileData.documents.length;
  document.getElementById('docsPreview').textContent = compactPreview(
    profileData.documents,
    doc => doc.file_name,
    'No knowledge sources yet. Open this section to upload a document or add a note.'
  );
  if (!profileData.documents.length) {
    container.innerHTML = '<div class="col-12"><div class="empty-state"><i class="bi bi-journal-richtext"></i>No knowledge sources yet. Upload a document or add a manual note.</div></div>';
    return;
  }
  const labels = { general: 'Knowledge', service: 'Service source', policy: 'Policy source' };
  container.innerHTML = profileData.documents.map(doc => `
    <div class="col-md-6 col-xl-4">
      <div class="doc-item h-100">
        <div class="doc-icon"><i class="bi ${doc.file_type?.includes('pdf') ? 'bi-file-earmark-pdf' : doc.file_type?.includes('word') ? 'bi-file-earmark-word' : 'bi-file-earmark-text'}"></i></div>
        <div class="doc-copy"><strong title="${EngageAI.escapeHtml(doc.file_name)}">${EngageAI.escapeHtml(doc.file_name)}</strong><small>${EngageAI.escapeHtml(labels[doc.document_type] || doc.document_type || 'Knowledge')}</small></div>
        <button class="btn btn-icon btn-soft btn-sm text-danger" type="button" onclick="deleteDoc('${doc.document_id}')" title="Delete document"><i class="bi bi-trash3"></i></button>
      </div>
    </div>`).join('');
}

function renderOrganization() {
  const org = profileData.organization;
  if (!org) return;
  document.getElementById('profileName').textContent = org.organization_name;
  document.getElementById('profileType').innerHTML = `<i class="bi bi-building"></i>${EngageAI.escapeHtml(org.organization_type)}`;
  document.getElementById('profileDescription').textContent = org.short_description;
  const form = document.getElementById('orgForm');
  form.organization_name.value = org.organization_name || '';
  form.organization_type.value = org.organization_type || '';
  form.short_description.value = org.short_description || '';
}

function renderWidgetIntegration() {
  if (!orgId) return;
  const link = `${EngageAI.API}/widget/embed.js?organization_id=${encodeURIComponent(orgId)}`;
  const embedCode = `<script src="${link}"><\/script>`;
  const linkInput = document.getElementById('widgetLink');
  const codeArea = document.getElementById('widgetEmbedCode');
  if (linkInput) linkInput.value = link;
  if (codeArea) codeArea.value = embedCode;
}

async function copyText(value, successMessage) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
    } else {
      const helper = document.createElement('textarea');
      helper.value = value;
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      helper.focus();
      helper.select();
      document.execCommand('copy');
      helper.remove();
    }
    EngageAI.toast(successMessage, 'success');
  } catch (_) {
    EngageAI.toast('Could not copy automatically. Select the text and copy it manually.', 'warning');
  }
}

function copyWidgetLink() {
  const value = document.getElementById('widgetLink')?.value || '';
  if (value) copyText(value, 'Widget link copied.');
}

function copyWidgetEmbedCode() {
  const value = document.getElementById('widgetEmbedCode')?.value || '';
  if (value) copyText(value, 'Website embed code copied.');
}

function refreshPolicySelect() {
  const select = document.querySelector('#policyForm [name=related_service_id]');
  const current = select.value;
  select.innerHTML = '<option value="">General / No related service</option>' + profileData.services.map(service =>
    `<option value="${EngageAI.escapeHtml(service.service_id)}">${EngageAI.escapeHtml(service.service_name)}${service.sub_service_name ? ` / ${EngageAI.escapeHtml(service.sub_service_name)}` : ''}</option>`
  ).join('');
  if ([...select.options].some(option => option.value === current)) select.value = current;
}

async function loadProfile() {
  try {
    const [organization, services, policies, documents] = await Promise.all([
      EngageAI.request(`/organizations/${orgId}`),
      EngageAI.request(`/services/${orgId}`),
      EngageAI.request(`/policies/${orgId}`),
      EngageAI.request(`/knowledge-documents/${orgId}`),
    ]);
    profileData = { organization, services, policies, documents };
    renderOrganization();
    renderWidgetIntegration();
    refreshPolicySelect();
    renderServices();
    renderPolicies();
    renderDocuments();
    renderLandingPageProfile(profileData.organization);
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

function openOrganizationModal() { renderOrganization(); modal('organizationModal').show(); }

async function saveOrg(event) {
  event.preventDefault();
  const button = document.getElementById('orgSaveBtn');
  EngageAI.setBusy(button, true, 'Saving...');
  try {
    profileData.organization = await EngageAI.request(`/organizations/${orgId}`, {
      method: 'PUT', body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))),
    });
    renderOrganization();
    modal('organizationModal').hide();
    EngageAI.toast('Organization information updated.', 'success');
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  } finally { EngageAI.setBusy(button, false); }
}

function openServiceModal(fromManager = false) {
  const form = document.getElementById('serviceForm');
  form.reset(); form.service_id.value = '';
  document.getElementById('serviceModalTitle').textContent = 'Add service';
  document.getElementById('serviceSaveBtn').textContent = 'Save Service';
  if (fromManager) openChildEditor('servicesManagerModal', 'serviceModal');
  else modal('serviceModal').show();
}

function editService(id) {
  const service = profileData.services.find(item => item.service_id === id);
  if (!service) return;
  const form = document.getElementById('serviceForm');
  ['service_id', 'service_name', 'sub_service_name', 'service_description', 'service_price', 'service_requirements'].forEach(key => form.elements[key].value = service[key] ?? '');
  document.getElementById('serviceModalTitle').textContent = 'Edit service';
  document.getElementById('serviceSaveBtn').textContent = 'Save Changes';
  if (document.getElementById('servicesManagerModal').classList.contains('show')) openChildEditor('servicesManagerModal', 'serviceModal');
  else modal('serviceModal').show();
}

async function saveService(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('serviceSaveBtn');
  const payload = Object.fromEntries(new FormData(form));
  const id = payload.service_id; delete payload.service_id;
  payload.service_price = payload.service_price || null;
  EngageAI.setBusy(button, true, 'Saving...');
  try {
    if (id) await EngageAI.request(`/services/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
    else await EngageAI.request('/services', { method: 'POST', body: JSON.stringify({ ...payload, organization_id: orgId }) });
    EngageAI.toast(id ? 'Service updated successfully.' : 'Service added successfully.', 'success');
    await loadProfile();
    modal('serviceModal').hide();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
  finally { EngageAI.setBusy(button, false); }
}

async function deleteService(id) {
  const service = profileData.services.find(item => item.service_id === id);
  const ok = await EngageAI.confirmAction({ title: 'Delete service?', message: `Delete “${service?.service_name || 'this service'}”? Related policies will become general.`, confirmText: 'Delete Service', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/services/${id}`, { method: 'DELETE' });
    EngageAI.toast('Service deleted.', 'success');
    await loadProfile();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

function openPolicyModal(fromManager = false) {
  const form = document.getElementById('policyForm');
  form.reset(); form.policy_id.value = ''; refreshPolicySelect();
  document.getElementById('policyModalTitle').textContent = 'Add policy';
  document.getElementById('policySaveBtn').textContent = 'Save Policy';
  if (fromManager) openChildEditor('policiesManagerModal', 'policyModal');
  else modal('policyModal').show();
}

function editPolicy(id) {
  const policy = profileData.policies.find(item => item.policy_id === id);
  if (!policy) return;
  refreshPolicySelect();
  const form = document.getElementById('policyForm');
  form.policy_id.value = policy.policy_id;
  form.policy_name.value = policy.policy_name || '';
  form.policy_description.value = policy.policy_description || '';
  form.related_service_id.value = policy.related_service_id || '';
  document.getElementById('policyModalTitle').textContent = 'Edit policy';
  document.getElementById('policySaveBtn').textContent = 'Save Changes';
  if (document.getElementById('policiesManagerModal').classList.contains('show')) openChildEditor('policiesManagerModal', 'policyModal');
  else modal('policyModal').show();
}

async function savePolicy(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('policySaveBtn');
  const payload = Object.fromEntries(new FormData(form));
  const id = payload.policy_id; delete payload.policy_id;
  payload.related_service_id = payload.related_service_id || null;
  EngageAI.setBusy(button, true, 'Saving...');
  try {
    if (id) await EngageAI.request(`/policies/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
    else await EngageAI.request('/policies', { method: 'POST', body: JSON.stringify({ ...payload, organization_id: orgId }) });
    EngageAI.toast(id ? 'Policy updated successfully.' : 'Policy added successfully.', 'success');
    await loadProfile();
    modal('policyModal').hide();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
  finally { EngageAI.setBusy(button, false); }
}

async function deletePolicy(id) {
  const policy = profileData.policies.find(item => item.policy_id === id);
  const ok = await EngageAI.confirmAction({ title: 'Delete policy?', message: `Delete “${policy?.policy_name || 'this policy'}”?`, confirmText: 'Delete Policy', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/policies/${id}`, { method: 'DELETE' });
    EngageAI.toast('Policy deleted.', 'success');
    await loadProfile();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

function openKnowledgeModal(fromManager = false) {
  document.getElementById('knowledgeUploadForm').reset();
  document.getElementById('knowledgeManualForm').reset();
  if (fromManager) openChildEditor('knowledgeManagerModal', 'knowledgeModal');
  else modal('knowledgeModal').show();
}

async function uploadDoc(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('knowledgeUploadBtn');
  const file = form.elements.file.files[0];
  if (!file) return EngageAI.toast('Choose a file first.', 'warning');
  EngageAI.setBusy(button, true, 'Uploading...');
  try {
    const body = new FormData();
    body.append('organization_id', orgId);
    body.append('document_type', 'general');
    body.append('file', file, file.name);
    await EngageAI.request('/knowledge-documents', { method: 'POST', body });
    form.reset();
    EngageAI.toast(`${file.name} uploaded and indexed successfully.`, 'success');
    await loadProfile();
    modal('knowledgeModal').hide();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
  finally { EngageAI.setBusy(button, false); }
}

async function saveManualKnowledge(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('manualKnowledgeBtn');
  const payload = Object.fromEntries(new FormData(form));
  EngageAI.setBusy(button, true, 'Saving...');
  try {
    await EngageAI.request('/knowledge-documents/manual', { method: 'POST', body: JSON.stringify({ organization_id: orgId, ...payload }) });
    form.reset();
    EngageAI.toast('Manual knowledge note added and indexed.', 'success');
    await loadProfile();
    modal('knowledgeModal').hide();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
  finally { EngageAI.setBusy(button, false); }
}

async function deleteDoc(id) {
  const doc = profileData.documents.find(item => item.document_id === id);
  const ok = await EngageAI.confirmAction({ title: 'Delete knowledge source?', message: `Delete “${doc?.file_name || 'this source'}” from the knowledge library?`, confirmText: 'Delete Source', danger: true });
  if (!ok) return;
  try {
    await EngageAI.request(`/knowledge-documents/${id}`, { method: 'DELETE' });
    EngageAI.toast('Knowledge source deleted.', 'success');
    await loadProfile();
  } catch (error) { EngageAI.toast(error.message, 'danger'); }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!EngageAI.requireAuth()) return;
  EngageAI.renderHeader();

  ['serviceModal', 'policyModal', 'knowledgeModal'].forEach(childId => {
    document.getElementById(childId).addEventListener('hidden.bs.modal', () => {
      if (!editorParent || editorParent.childId !== childId) return;
      const parentId = editorParent.parentId;
      editorParent = null;
      window.setTimeout(() => modal(parentId).show(), 120);
    });
  });

  loadProfile();
});

function renderLandingPageProfile(organization) {
  const host = document.getElementById('landingPageProfile');
  if (!host) return;

  const organizationId = localStorage.getItem('organization_id');

  if (!organization.landing_page_enabled) {
    host.innerHTML = `
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <span class="text-muted">
          Landing page not published.
        </span>

        <button
          type="button"
          class="btn btn-success btn-sm"
          onclick="publishLandingPage()"
        >
          <i class="bi bi-globe2 me-1"></i>
          Publish
        </button>
      </div>
    `;
    return;
  }

  const pageUrl =
    `${window.location.origin}/landing-page.html?organization_id=${organizationId}`;

  host.innerHTML = `
    <div class="d-flex align-items-center gap-2 flex-wrap">

      <span class="badge bg-success">Published</span>

      <a
        href="${pageUrl}"
        target="_blank"
        class="btn btn-soft btn-sm"
      >
        <i class="bi bi-box-arrow-up-right me-1"></i>
        View Landing Page
      </a>

      <button
        type="button"
        class="btn btn-outline-secondary btn-sm"
        onclick="copyLandingPageLink('${pageUrl}')"
      >
        <i class="bi bi-copy me-1"></i>
        Copy Link
      </button>

      <button
        type="button"
        class="btn btn-outline-danger btn-sm"
        onclick="unpublishLandingPage()"
      >
        <i class="bi bi-eye-slash me-1"></i>
        Unpublish
      </button>

    </div>
  `;

}

async function publishLandingPage() {
  try {
    profileData.organization = await EngageAI.request(
      `/organizations/${orgId}`,
      {
        method: 'PUT',
        body: JSON.stringify({
          landing_page_enabled: true
        })
      }
    );

    renderLandingPageProfile(profileData.organization);
    EngageAI.toast('Landing page published.', 'success');

  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

async function unpublishLandingPage() {
  try {
    profileData.organization = await EngageAI.request(
      `/organizations/${orgId}`,
      {
        method: 'PUT',
        body: JSON.stringify({
          landing_page_enabled: false
        })
      }
    );

    renderLandingPageProfile(profileData.organization);
    EngageAI.toast('Landing page unpublished.', 'success');

  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

function copyLandingPageLink(url) {
  copyText(url, 'Landing page link copied.');
}