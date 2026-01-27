import os
import requests

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SMTP_USER")  # verified sender email in SendGrid


def send_approval_email(
    to_emails,
    approve_url,
    reject_url,
    expense,
    submitted_by_name,
    submitted_by_email
):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not set")

    subject = "Expense Approval Required"

    def row(label, value):
        return f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;"><b>{label}</b></td>
            <td style="padding:8px;border:1px solid #ddd;">{value if value not in (None, "") else "-"}</td>
        </tr>
        """

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>New Expense Submitted</h2>

        <p>
            <b>Submitted by:</b> {submitted_by_name}<br>
            <b>Email:</b> {submitted_by_email}
        </p>

        <table style="border-collapse: collapse; width: 100%; margin-top: 15px;">
            {row("Client", expense.client)}
            {row("Office", expense.office_name)}
            {row("Expense Date", expense.expense_date)}
            {row("Head", expense.head)}
            {row("Subhead", expense.subhead)}
            {row("From Location", expense.from_location)}
            {row("To Location", expense.to_location)}
            {row("Weight", expense.weight)}
            {row("Amount", expense.amount)}
            {row("AWB", expense.awb)}
            {row("Vehicle Type", expense.vehicle_type)}
            {row("Remark", expense.remark)}
        </table>

        <div style="margin-top: 25px;">
            <a href="{approve_url}"
               style="
                   padding:10px 16px;
                   background:#28a745;
                   color:white;
                   text-decoration:none;
                   border-radius:5px;
                   font-weight:bold;
                   margin-right:10px;
               ">
                ✅ APPROVE
            </a>

            <a href="{reject_url}"
               style="
                   padding:10px 16px;
                   background:#dc3545;
                   color:white;
                   text-decoration:none;
                   border-radius:5px;
                   font-weight:bold;
               ">
                ❌ REJECT
            </a>
        </div>

        <p style="margin-top:20px; font-size:12px; color:#777;">
            Note: This approval link is valid for 24 hours.
        </p>
    </body>
    </html>
    """

    payload = {
        "personalizations": [
            {
                "to": [{"email": e} for e in to_emails],
                "subject": subject
            }
        ],
        "from": {"email": FROM_EMAIL},
        "content": [
            {
                "type": "text/html",
                "value": html_content
            }
        ]
    }

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    if response.status_code not in (200, 202):
        raise RuntimeError(
            f"SendGrid error: {response.status_code} {response.text}"
        )
