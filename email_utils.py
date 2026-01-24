import os
import requests

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SMTP_USER")  # reuse your verified email

def send_approval_email(to_emails, approve_url, reject_url, expense, submitted_by):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not set")

    subject = "Expense Approval Required"

    html_content = f"""
    <h3>New Expense Submitted</h3>
    <p><b>Submitted by:</b> {submitted_by}</p>
    <p><b>Client:</b> {expense.client}</p>
    <p><b>Office:</b> {expense.office_name}</p>
    <p><b>Head:</b> {expense.head}</p>
    <p><b>Amount:</b> {expense.amount}</p>

    <br>

    <a href="{approve_url}"
       style="padding:10px 15px;background:green;color:white;text-decoration:none;">
       APPROVE
    </a>

    &nbsp;&nbsp;

    <a href="{reject_url}"
       style="padding:10px 15px;background:red;color:white;text-decoration:none;">
       REJECT
    </a>
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
        raise RuntimeError(f"SendGrid error: {response.status_code} {response.text}")
