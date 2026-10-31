/* Shared chrome for the Acme Suite demo app. */
window.ACME = {
  version: '2.4.0',
  user: { name: 'Priya Raman', email: 'priya@northwind.example', role: 'member' },
};

function renderChrome(active) {
  const u = window.ACME.user;
  document.body.insertAdjacentHTML(
    'afterbegin',
    `<header>
       <span class="logo">Acme Suite</span>
       <nav>
         <a href="/demo/billing/" class="${active === 'billing' ? 'active' : ''}">Billing</a>
         <a href="/demo/projects/" class="${active === 'projects' ? 'active' : ''}">Projects</a>
         <a href="/demo/analytics/" class="${active === 'analytics' ? 'active' : ''}">Analytics</a>
         <a href="/demo/settings/payment/" class="${active === 'settings' ? 'active' : ''}">Settings</a>
       </nav>
       <div class="who">
         <div data-private>${u.name}</div>
         <div data-private>${u.email}</div>
       </div>
     </header>`
  );
}
