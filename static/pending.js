const tableBody = document.querySelector("#pendingTable tbody");
const emptyMessage = document.getElementById("emptyMessage");

// Load pending expenses on page load
document.addEventListener("DOMContentLoaded", loadPendingExpenses);

async function loadPendingExpenses() {
    tableBody.innerHTML = "";
    emptyMessage.style.display = "none";

    try {
        const res = await fetch("/api/admin/pending-expenses", {
            credentials: "include"
        });

        if (res.status === 403) {
            alert("Access denied. Admins only.");
            window.location.href = "/static/dashboard.html";
            return;
        }

        const data = await res.json();

        if (!data.length) {
            emptyMessage.style.display = "block";
            return;
        }

        data.forEach(exp => {
            const tr = document.createElement("tr");

            tr.innerHTML = `
                <td>${exp.submitted_by_name}</td>
                <td>${exp.client}</td>
                <td>${exp.office}</td>
                <td>${exp.head}</td>
                <td>${exp.subhead ?? "-"}</td>
                <td>${exp.amount ?? "-"}</td>
                <td>${exp.expense_date ?? "-"}</td>
                <td>
                    <button class="btn btn-approve">Approve</button>
                    <button class="btn btn-reject">Reject</button>
                </td>
            `;

            const approveBtn = tr.querySelector(".btn-approve");
            const rejectBtn  = tr.querySelector(".btn-reject");

            approveBtn.onclick = () => handleAction(
                exp.pending_id,
                "approve",
                tr
            );

            rejectBtn.onclick = () => handleAction(
                exp.pending_id,
                "reject",
                tr
            );

            tableBody.appendChild(tr);
        });

    } catch (err) {
        console.error(err);
        alert("Failed to load pending expenses.");
    }
}

async function handleAction(pendingId, action, rowElement) {
    const confirmMsg =
        action === "approve"
            ? "Approve this expense?"
            : "Reject this expense?";

    if (!confirm(confirmMsg)) return;

    try {
        const res = await fetch(
            `/api/admin/pending-expenses/${pendingId}/${action}`,
            {
                method: "POST",
                credentials: "include"
            }
        );

        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Action failed");
            return;
        }

        // Remove row from table
        rowElement.remove();

        // Show empty message if no rows left
        if (!tableBody.children.length) {
            emptyMessage.style.display = "block";
        }

    } catch (err) {
        console.error(err);
        alert("Server error while processing request.");
    }
}
