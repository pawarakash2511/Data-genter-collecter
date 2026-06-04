const API_LOGIN     = "/api/admin/login";
const API_CUSTOMERS = "/api/admin/customers";

function getToken()        { return sessionStorage.getItem("admin_token"); }
function setToken(t)       { sessionStorage.setItem("admin_token", t); }
function clearToken()      { sessionStorage.removeItem("admin_token"); }

function showLogin() {
  document.getElementById("loginSection").style.display    = "flex";
  document.getElementById("dashboardSection").style.display = "none";
}

function showDashboard() {
  document.getElementById("loginSection").style.display    = "none";
  document.getElementById("dashboardSection").style.display = "block";
}

window.addEventListener("DOMContentLoaded", () => {
  if (getToken()) {
    showDashboard();
    loadCustomers();
  } else {
    showLogin();
  }
});

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const msg      = document.getElementById("loginMsg");

  msg.textContent = "Logging in...";
  msg.className   = "info";

  try {
    const res  = await fetch(API_LOGIN, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ username, password }),
    });
    const data = await res.json();

    if (res.ok) {
      setToken(data.token);
      msg.textContent = "";
      msg.className   = "";
      showDashboard();
      loadCustomers();
    } else {
      msg.textContent = data.message || "Login failed";
      msg.className   = "error";
    }
  } catch {
    msg.textContent = "Network error — please try again";
    msg.className   = "error";
  }
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  document.getElementById("loginForm").reset();
  document.getElementById("loginMsg").textContent = "";
  document.getElementById("loginMsg").className   = "";
  showLogin();
});

document.getElementById("refreshBtn").addEventListener("click", loadCustomers);

async function loadCustomers() {
  const tbody    = document.getElementById("customerTableBody");
  const countEl  = document.getElementById("recordCount");

  tbody.innerHTML = `<tr><td colspan="7" class="loading">Loading...</td></tr>`;
  countEl.textContent = "Loading...";

  try {
    const res = await fetch(API_CUSTOMERS, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (res.status === 401) {
      clearToken();
      showLogin();
      return;
    }

    const data      = await res.json();
    const customers = data.data || [];
    const count     = data.count ?? customers.length;

    countEl.textContent = `${count} record${count !== 1 ? "s" : ""}`;

    if (customers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty">No records submitted yet</td></tr>`;
      return;
    }

    tbody.innerHTML = customers
      .map((c, i) => `
        <tr class="${i % 2 === 0 ? "even" : "odd"}">
          <td>${c.id}</td>
          <td>${esc(c.customer_id)}</td>
          <td>${esc(c.customer_name)}</td>
          <td>${esc(c.gender)}</td>
          <td>${c.age}</td>
          <td>${c.some_number}</td>
          <td>${esc(c.submitted_at)}</td>
        </tr>
      `)
      .join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="7" class="error-cell">Failed to load records — check your connection</td></tr>`;
    countEl.textContent = "Error";
  }
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
