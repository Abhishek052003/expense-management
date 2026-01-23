import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def send_approval_email(to_list, approve_url, reject_url, payload, submitted_by):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Expense Approval Required – {payload.client}"
    msg["From"] = SMTP_USER
    msg["To"] = ",".join(to_list)

    html = f"""
    <h2>New Expense Submitted</h2>
    <b>Submitted By:</b> {submitted_by}<br><br>

    <b>Client:</b> {payload.client}<br>
    <b>Amount:</b> {payload.amount}<br>
    <b>Head:</b> {payload.head}<br><br>

    <a href="{approve_url}" style="padding:10px 18px;background:#22c55e;color:white;text-decoration:none;border-radius:5px;">APPROVE</a>
    &nbsp;&nbsp;
    <a href="{reject_url}" style="padding:10px 18px;background:#ef4444;color:white;text-decoration:none;border-radius:5px;">REJECT</a>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_list, msg.as_string())
