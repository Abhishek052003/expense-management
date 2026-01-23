from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from database import get_db
from auth import hash_password, verify_password, create_token
from fastapi.staticfiles import StaticFiles
from fastapi import Request, Depends
from auth import decode_token
from pydantic import BaseModel
from auth import hash_password
import uuid
from datetime import datetime, timedelta
from email_utils import send_approval_email
import os

BASE_URL = os.getenv("BASE_URL", "")
ENV = os.getenv("ENV", "development")
IS_PROD = ENV == "production"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class CreateUserIn(BaseModel):
    name: str
    email: str
    password: str
    role: str


class ExpenseIn(BaseModel):
    expense_date: str | None = None
    client: str
    office_name: str
    head: str
    subhead: str
    from_location: str | None = None
    to_location: str | None = None
    weight: float | None = None
    amount: float | None = None
    awb: str | None = None
    remark: str | None = None
    vehicle_type: str | None = None

# Create users table
@app.on_event("startup")
def create_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    """)
    conn.commit()
    cur.close()
    conn.close()

class User(BaseModel):
    email: str
    password: str

@app.post("/register")
def register(user: User):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s", (user.email,))
    if cur.fetchone():
        raise HTTPException(400, "User exists")

    cur.execute("INSERT INTO users(email,password) VALUES(%s,%s)",
                (user.email, hash_password(user.password)))

    conn.commit()
    cur.close()
    conn.close()
    return {"msg": "User created"}

@app.post("/login")
def login(user: User, response: Response):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id,password FROM users WHERE email=%s", (user.email,))
    row = cur.fetchone()

    if not row or not verify_password(user.password, row[1]):
        raise HTTPException(401, "Invalid credentials")

    token = create_token({"user_id": row[0]})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=IS_PROD,
        samesite="none" if IS_PROD else "lax"
    )


    return {"msg": "Login success"}


def get_current_user(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(401, "Not logged in")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,name,email,role FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        raise HTTPException(401, "User not found")

    return {"id": user[0], "name": user[1],"email": user[2], "role": user[3]}

@app.get("/me")
def read_me(current_user=Depends(get_current_user)):
    return current_user

@app.post("/api/admin/create-user")
def create_user(data: CreateUserIn, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s", (data.email,))
    if cur.fetchone():
        raise HTTPException(400, "User already exists")

    cur.execute("""
        INSERT INTO users (name,email,password,role)
        VALUES (%s,%s,%s,%s)
    """, (data.name,data.email, hash_password(data.password), data.role))

    conn.commit()
    cur.close()
    conn.close()

    return {"msg": "User created successfully"}

@app.post("/api/expenses/submit")
def submit_expense(data: ExpenseIn, current_user=Depends(get_current_user)):

    if data.head in ["Porter", "Urgent Delivery", "Pickup & Delivery"]:
        if not all([data.from_location, data.to_location, data.weight, data.amount, data.awb]):
            raise HTTPException(
                400,
                "From, To, Weight, Amount and AWB are mandatory for this expense type"
            )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO pending_expenses (
          expense_date, client, office_name, head, subhead,
          from_location, to_location, weight, amount, awb,
          remark, vehicle_type, created_by
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        data.expense_date,
        data.client,
        data.office_name,
        data.head,
        data.subhead,
        data.from_location,
        data.to_location,
        data.weight,
        data.amount,
        data.awb,
        data.remark,
        data.vehicle_type,
        current_user["id"]
    ))

    pending_id = cur.fetchone()[0]

    approve_token = create_approval_token(cur, pending_id, "approve")
    reject_token  = create_approval_token(cur, pending_id, "reject")

    # ---------------- MAIL TRIGGER ----------------
    cur.execute("""
        SELECT email FROM users
        WHERE role = 'admin'
    """)
    emails = [r[0] for r in cur.fetchall()]

    approve_url = f"{BASE_URL}/review/approve/{approve_token}"
    reject_url  = f"{BASE_URL}/review/reject/{reject_token}"


    send_approval_email(
        emails,
        approve_url,
        reject_url,
        data,
        current_user["email"]
    )
    # ------------------------------------------------

    conn.commit()
    cur.close()
    conn.close()

    return {"msg": "Expense submitted for approval"}



def create_approval_token(cur, pending_id: int, action: str):
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=24)

    cur.execute("""
        INSERT INTO approval_tokens (token, pending_id, action, expires_at)
        VALUES (%s,%s,%s,%s)
    """, (token, pending_id, action, expires))

    return token


# ===================== NEW APPROVAL LOGIC =====================

def validate_token(cur, token: str, action: str):
    cur.execute("""
        SELECT id, pending_id, is_used, expires_at
        FROM approval_tokens
        WHERE token=%s AND action=%s
    """, (token, action))

    row = cur.fetchone()
    if not row:
        raise HTTPException(400, "Invalid token")

    token_id, pending_id, is_used, expires_at = row
    if is_used:
        raise HTTPException(400, "Token already used")
    if datetime.utcnow() > expires_at:
        raise HTTPException(400, "Token expired")

    return token_id, pending_id


@app.get("/review/approve/{token}")
def approve_expense(token: str):
    conn = get_db()
    cur = conn.cursor()
    try:
        token_id, pending_id = validate_token(cur, token, "approve")

        cur.execute("SELECT * FROM pending_expenses WHERE id=%s", (pending_id,))
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))

        cur.execute("""
            INSERT INTO expenses (expense_date,client,office_name,head,subhead,
            from_location,to_location,weight,amount,awb,remark,vehicle_type,created_by)
            VALUES (%(expense_date)s,%(client)s,%(office_name)s,%(head)s,%(subhead)s,
                    %(from_location)s,%(to_location)s,%(weight)s,%(amount)s,%(awb)s,
                    %(remark)s,%(vehicle_type)s,%(created_by)s)
        """, data)

        cur.execute("DELETE FROM pending_expenses WHERE id=%s", (pending_id,))
        cur.execute("UPDATE approval_tokens SET is_used=true, used_at=NOW() WHERE id=%s", (token_id,))
        conn.commit()
        return {"status": "approved"}
    except:
        conn.rollback()
        raise


@app.get("/review/reject/{token}")
def reject_expense(token: str):
    conn = get_db()
    cur = conn.cursor()
    try:
        token_id, pending_id = validate_token(cur, token, "reject")

        cur.execute("SELECT * FROM pending_expenses WHERE id=%s", (pending_id,))
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))

        cur.execute("""
            INSERT INTO rejected_expenses (expense_date,client,office_name,head,subhead,
            from_location,to_location,weight,amount,awb,remark,vehicle_type,created_by)
            VALUES (%(expense_date)s,%(client)s,%(office_name)s,%(head)s,%(subhead)s,
                    %(from_location)s,%(to_location)s,%(weight)s,%(amount)s,%(awb)s,
                    %(remark)s,%(vehicle_type)s,%(created_by)s)
        """, data)

        cur.execute("DELETE FROM pending_expenses WHERE id=%s", (pending_id,))
        cur.execute("UPDATE approval_tokens SET is_used=true, used_at=NOW() WHERE id=%s", (token_id,))
        conn.commit()
        return {"status": "rejected"}
    except:
        conn.rollback()
        raise

@app.get("/api/dashboard/kpis")
def dashboard_kpis(
    user: str | None = None,
    office: str | None = None,
    head: str | None = None,
    subhead: str | None = None,
    date: str | None = None,
    current_user=Depends(get_current_user)
):
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    values = []

    if current_user["role"] == "admin":
        # Apply filters ONLY for admin
        if user not in (None, ""):
            conditions.append("created_by = %s")
            values.append(int(user))

        if office not in (None, ""):
            conditions.append("office_name = %s")
            values.append(office)

        if head not in (None, ""):
            conditions.append("head = %s")
            values.append(head)

        if subhead not in (None, ""):
            conditions.append("subhead = %s")
            values.append(subhead)

        if date not in (None, ""):
            conditions.append("expense_date = %s")
            values.append(date)
    else:
        # Normal user → always own data
        conditions.append("created_by = %s")
        values.append(current_user["id"])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Approved amount
    cur.execute(f"""
        SELECT COALESCE(SUM(amount),0)
        FROM expenses
        {where_clause}
    """, values)
    total_expense = cur.fetchone()[0]

    # Pending count
    cur.execute(f"""
        SELECT COUNT(*)
        FROM pending_expenses
        {where_clause}
    """, values)
    total_pending = cur.fetchone()[0]

    # Approved count
    cur.execute(f"""
        SELECT COUNT(*)
        FROM expenses
        {where_clause}
    """, values)
    total_approved = cur.fetchone()[0]

    # Rejected count
    cur.execute(f"""
        SELECT COUNT(*)
        FROM rejected_expenses
        {where_clause}
    """, values)
    total_rejected = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "total_expense": total_expense,
        "total_uploaded": total_pending + total_approved + total_rejected,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "total_pending": total_pending
    }


@app.get("/api/dashboard/expenses/{status}")
def user_expenses(status: str, current_user=Depends(get_current_user)):
    conn = get_db()
    cur = conn.cursor()

    user_id = current_user["id"]

    if status == "approved":
        table = "expenses"
    elif status == "pending":
        table = "pending_expenses"
    elif status == "rejected":
        table = "rejected_expenses"
    else:
        raise HTTPException(400, "Invalid status")

    cur.execute(f"""
        SELECT expense_date, head, subhead, amount
        FROM {table}
        WHERE created_by = %s
        ORDER BY expense_date DESC
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "date": r[0],
            "head": r[1],
            "subhead": r[2],
            "amount": r[3]
        } for r in rows
    ]

@app.get("/api/dashboard/admin/filters")
def admin_filters(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only")

    conn = get_db()
    cur = conn.cursor()

    # Users (id + email)
    cur.execute("""
        SELECT DISTINCT u.id, COALESCE(u.name, u.email)
        FROM users u
        JOIN expenses e ON e.created_by = u.id
        ORDER BY COALESCE(u.name, u.email)
    """)
    users = [{"id": r[0], "label": r[1]} for r in cur.fetchall()]

    # Offices
    cur.execute("""
        SELECT DISTINCT office_name
        FROM expenses
        WHERE office_name IS NOT NULL
        ORDER BY office_name
    """)
    offices = [r[0] for r in cur.fetchall()]

    # Heads
    cur.execute("""
        SELECT DISTINCT head
        FROM expenses
        WHERE head IS NOT NULL
        ORDER BY head
    """)
    heads = [r[0] for r in cur.fetchall()]

    # Subheads
    cur.execute("""
        SELECT DISTINCT subhead
        FROM expenses
        WHERE subhead IS NOT NULL
        ORDER BY subhead
    """)
    subheads = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()

    return {
        "users": users,
        "offices": offices,
        "heads": heads,
        "subheads": subheads
    }

@app.get("/api/dashboard/admin/pie/head")
def admin_pie_head(
    user: str | None = None,
    office: str | None = None,
    head: str | None = None,
    subhead: str | None = None,
    date: str | None = None,
    top: int = 3,
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only")

    conditions = []
    values = []

    if user not in (None, ""):
        conditions.append("created_by = %s")
        values.append(int(user))

    if office not in (None, ""):
        conditions.append("office_name = %s")
        values.append(office)

    if head not in (None, ""):
        conditions.append("head = %s")
        values.append(head)

    if subhead not in (None, ""):
        conditions.append("subhead = %s")
        values.append(subhead)

    if date not in (None, ""):
        conditions.append("expense_date = %s")
        values.append(date)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT head, SUM(amount)
        FROM expenses
        {where_clause}
        GROUP BY head
        ORDER BY SUM(amount) DESC
        LIMIT %s
    """, (*values, top))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [{"label": r[0], "value": float(r[1])} for r in rows]


@app.get("/api/dashboard/admin/pie/office")
def admin_pie_office(
    user: str | None = None,
    office: str | None = None,
    head: str | None = None,
    subhead: str | None = None,
    date: str | None = None,
    top: int = 3,
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Admins only")

    conditions = []
    values = []

    if user not in (None, ""):
        conditions.append("created_by = %s")
        values.append(int(user))

    if office not in (None, ""):
        conditions.append("office_name = %s")
        values.append(office)

    if head not in (None, ""):
        conditions.append("head = %s")
        values.append(head)

    if subhead not in (None, ""):
        conditions.append("subhead = %s")
        values.append(subhead)

    if date not in (None, ""):
        conditions.append("expense_date = %s")
        values.append(date)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT office_name, SUM(amount)
        FROM expenses
        {where_clause}
        GROUP BY office_name
        ORDER BY SUM(amount) DESC
        LIMIT %s
    """, (*values, top))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {"label": r[0], "value": float(r[1])}
        for r in rows
    ]
