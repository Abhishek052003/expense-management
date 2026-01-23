from email_utils import send_approval_email

class Dummy:
    client = "Test Client"
    amount = 100
    head = "Testing"

send_approval_email(
    ["dhokareabhi@gmail.com"],
    "https://google.com",
    "https://google.com",
    Dummy(),
    "testuser@gmail.com"
)

print("Mail sent")
