let headChart = null;
let officeChart = null;

async function fetchMe(){
  const r = await fetch("/me");
  return r.json();
}

window.onload = async () => {
  const me = await fetchMe();
  await loadKPIs();

  await attachPendingClickIfAdmin();

  if (me.role === "admin") {
    document.getElementById("admin-section").classList.remove("hide");

    await loadAdminFilters();
    await loadHeadPie();
    await loadOfficePie();

  } else {
    document.getElementById("user-section").classList.remove("hide");

    await loadTable("approved", "approved-table");
    await loadTable("pending", "pending-table");
    await loadTable("rejected", "rejected-table");
  }
};



function logout(){
  document.cookie = "access_token=;expires=Thu, 01 Jan 1970 00:00:00 UTC;";
  window.location.href = "/static/login.html";
}

async function loadKPIs(){
  const params = new URLSearchParams({
    user: document.getElementById("f-user")?.value || "",
    office: document.getElementById("f-office")?.value || "",
    head: document.getElementById("f-head")?.value || "",
    subhead: document.getElementById("f-subhead")?.value || "",
    date: document.getElementById("f-date")?.value || ""
  });

  const res = await fetch(`/api/dashboard/kpis?${params}`);
  const d = await res.json();

  const kpis = [
    ["Total Expense", d.total_expense],
    ["Total Uploaded", d.total_uploaded],
    ["Approved", d.total_approved],
    ["Rejected", d.total_rejected],
    ["Pending", d.total_pending],
  ];

  const box = document.getElementById("kpis");
  box.innerHTML = "";

  kpis.forEach(k => {
    const div = document.createElement("div");
    div.className = "card center";

  // 👇 Make Pending KPI identifiable
    if (k[0] === "Pending") {
      div.id = "pendingCard";
    }

    div.innerHTML = `<h4>${k[0]}</h4><h2>${k[1]}</h2>`;
    box.appendChild(div);
  });

}


async function loadTable(status, tableId){
  const res = await fetch(`/api/dashboard/expenses/${status}`);
  const data = await res.json();

  const emptyBox = document.getElementById(`${status}-empty`);

  if(data.length === 0){
    document.getElementById(tableId).innerHTML = "";
    emptyBox.classList.remove("hide");
    return;
  }

  emptyBox.classList.add("hide");

  let html = `
    <tr>
      <th>Date</th>
      <th>Head</th>
      <th>Subhead</th>
      <th>Amount</th>
    </tr>
  `;

  data.forEach(r => {
    html += `
      <tr>
        <td>${r.date || ""}</td>
        <td>${r.head}</td>
        <td>${r.subhead}</td>
        <td>${r.amount}</td>
      </tr>
    `;
  });

  document.getElementById(tableId).innerHTML = html;
}

async function loadAdminFilters(){
  const res = await fetch("/api/dashboard/admin/filters");
  const data = await res.json();

  // User filter
  const userSel = document.getElementById("f-user");
  userSel.innerHTML = `<option value="">All Users</option>`;
  data.users.forEach(u => {
    userSel.innerHTML += `<option value="${u.id}">${u.label}</option>`;
  });

  // Office filter
  const officeSel = document.getElementById("f-office");
  officeSel.innerHTML = `<option value="">All Offices</option>`;
  data.offices.forEach(o => {
    officeSel.innerHTML += `<option value="${o}">${o}</option>`;
  });

  // Head filter
  const headSel = document.getElementById("f-head");
  headSel.innerHTML = `<option value="">All Heads</option>`;
  data.heads.forEach(h => {
    headSel.innerHTML += `<option value="${h}">${h}</option>`;
  });

  // Subhead filter
  const subSel = document.getElementById("f-subhead");
  subSel.innerHTML = `<option value="">All Subheads</option>`;
  data.subheads.forEach(s => {
    subSel.innerHTML += `<option value="${s}">${s}</option>`;
  });
}

async function loadHeadPie(){
  const params = new URLSearchParams({
    user: document.getElementById("f-user").value,
    office: document.getElementById("f-office").value,
    head: document.getElementById("f-head").value,
    subhead: document.getElementById("f-subhead").value,
    date: document.getElementById("f-date").value,
    top: document.getElementById("head-top").value
  });

  const res = await fetch(`/api/dashboard/admin/pie/head?${params}`);
  const data = await res.json();

  const labels = data.map(d => d.label);
  const values = data.map(d => d.value);

  if(headChart){
    headChart.destroy();
  }

  headChart = new Chart(
    document.getElementById("head-chart"),
    {
      type: "pie",
      data: {
        labels,
        datasets: [{
          data: values
        }]
      }
    }
  );
}

[
  "f-user",
  "f-office",
  "f-head",
  "f-subhead",
  "f-date",
  "head-top",
  "office-top"
].forEach(id => {
  document.getElementById(id)
    .addEventListener("change", () => {
      loadHeadPie();
      loadOfficePie();
      loadKPIs();
    });
});


  async function loadOfficePie(){
  const params = new URLSearchParams({
    user: document.getElementById("f-user").value,
    office: document.getElementById("f-office").value,
    head: document.getElementById("f-head").value,
    subhead: document.getElementById("f-subhead").value,
    date: document.getElementById("f-date").value,
    top: document.getElementById("office-top").value
  });

  const res = await fetch(`/api/dashboard/admin/pie/office?${params}`);
  const data = await res.json();

  const labels = data.map(d => d.label);
  const values = data.map(d => d.value);

  if (officeChart) {
    officeChart.destroy();
  }

  officeChart = new Chart(
    document.getElementById("office-chart"),
    {
      type: "pie",
      data: {
        labels,
        datasets: [{
          data: values
        }]
      }
    }
  );
}

async function attachPendingClickIfAdmin() {
  try {
    const me = await fetchMe();

    if (me.role === "admin") {
      const pendingCard = document.getElementById("pendingCard");

      if (pendingCard) {
        pendingCard.style.cursor = "pointer";
        pendingCard.title = "View pending approvals";

        pendingCard.addEventListener("click", () => {
          window.location.href = "/static/pending.html";
        });
      }
    }
  } catch (err) {
    console.error("Failed to attach pending click", err);
  }
}
