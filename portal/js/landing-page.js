const params = new URLSearchParams(window.location.search);
const organizationId = params.get('organization_id');

async function loadLandingPage() {
  if (!organizationId) {
    console.error('organization_id is missing');
    return;
  }

  try {
    const [orgResponse, servicesResponse] = await Promise.all([
      fetch(`https://engageai-backend-zhki.onrender.com/organizations/${organizationId}`),
      fetch(`https://engageai-backend-zhki.onrender.com/services/${organizationId}`)
    ]);

    if (!orgResponse.ok || !servicesResponse.ok) {
      throw new Error('Could not load landing page data');
    }

    const organization = await orgResponse.json();
    if (!organization.landing_page_enabled) {
        document.body.innerHTML = `
            <div class="container text-center py-5">
            <h2>Landing Page Not Published</h2>
            <p class="text-muted">
                This organization has not published its landing page yet.
            </p>
            </div>
        `;
        return;
    }
    const services = await servicesResponse.json();

    document.getElementById('pageTitle').textContent =
      organization.organization_name;

    document.getElementById('organizationNameNav').textContent =
      organization.organization_name;

    document.getElementById('organizationName').textContent =
      organization.organization_name;

    document.getElementById('organizationDescription').textContent =
      organization.short_description;

    const container = document.getElementById('servicesContainer');
    container.innerHTML = '';

    services.forEach(service => {
      container.innerHTML += `
        <div class="col-md-4">
          <div class="card h-100">
            <div class="card-body">
              <h4>${service.service_name}</h4>

              ${
                service.sub_service_name
                  ? `<h6>${service.sub_service_name}</h6>`
                  : ''
              }

              <p>${service.service_description}</p>

              ${
                service.service_price !== null
                  ? `<strong>PKR ${service.service_price}</strong>`
                  : ''
              }
            </div>
          </div>
        </div>
      `;
    });

    // Widget config
    window.ENGAGEAI_WIDGET_CONFIG = {
        organizationId: organizationId,
        organizationName: organization.organization_name,
        apiBaseUrl: 'https://engageai-backend-zhki.onrender.com',
        widgetCssUrl: 'https://engageai-backend-zhki.onrender.com/widget/widget.css'
    };

    const widgetScript = document.createElement('script');
    widgetScript.src = 'https://engageai-backend-zhki.onrender.com/widget/widget.js';
    document.body.appendChild(widgetScript);

  } catch (error) {
    console.error(error);
  }

  
}



document.addEventListener('DOMContentLoaded', loadLandingPage);