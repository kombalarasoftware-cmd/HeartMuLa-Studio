"""
Authentication service for HeartMuLa Studio.

Flow:
1. User registers with name + email
2. Admin (ADMIN_EMAIL) receives approval link
3. Admin clicks approve -> user gets activation email
4. User clicks activation link -> account activated
5. On login, 8-char code sent to user's email
6. User enters code -> JWT token issued
"""

import os
import secrets
import smtplib
import asyncio
import bcrypt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import Session, select

import jwt as pyjwt

from backend.app.models import User, UserStatus, VerificationCode, CodeType

# Config
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "cmutlu2006@hotmail.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_urlsafe(64))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
CODE_EXPIRE_MINUTES = 10
CODE_LENGTH = 8


SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "cenani@simmaxi.com")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "CeyTarBarEMi@")
SUPER_ADMIN_NAME = os.environ.get("SUPER_ADMIN_NAME", "Super Admin")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> Optional[dict]:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


def send_email(to: str, subject: str, html_body: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[Auth] SMTP not configured. Email to {to}: {subject}")
        print(f"[Auth] Body preview: {html_body[:200]}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], to, msg.as_string())

        print(f"[Auth] Email sent to {to}: {subject}")
        return True
    except Exception as e:
        print(f"[Auth] Email send failed: {e}")
        return False


def send_email_async(to: str, subject: str, html_body: str):
    import threading
    threading.Thread(target=send_email, args=(to, subject, html_body), daemon=True).start()


# --- Email Templates ---

def email_admin_approval(user_name: str, user_email: str, token: str) -> tuple[str, str]:
    subject = f"[HeartMuLa] New Registration: {user_name}"
    approve_url = f"{APP_URL}/auth/approve?token={token}"
    reject_url = f"{APP_URL}/auth/reject?token={token}"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #f1f5f9; padding: 40px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #22c55e; font-size: 28px; margin: 0;">HeartMuLa Studio</h1>
            <p style="color: #94a3b8; margin-top: 8px;">New User Registration</p>
        </div>
        <div style="background: rgba(255,255,255,0.05); border-radius: 12px; padding: 24px; margin-bottom: 24px;">
            <p style="margin: 0 0 8px 0;"><strong>Name:</strong> {user_name}</p>
            <p style="margin: 0;"><strong>Email:</strong> {user_email}</p>
        </div>
        <div style="text-align: center;">
            <a href="{approve_url}" style="display: inline-block; background: #22c55e; color: #000; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-right: 12px;">Approve</a>
            <a href="{reject_url}" style="display: inline-block; background: #ef4444; color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600;">Reject</a>
        </div>
        <p style="color: #64748b; font-size: 12px; text-align: center; margin-top: 30px;">HeartMuLa Studio - AI Music Creation</p>
    </div>
    """
    return subject, html


def email_user_activation(user_name: str, token: str) -> tuple[str, str]:
    subject = "Welcome to HeartMuLa Studio - Activate Your Account"
    activate_url = f"{APP_URL}/auth/activate?token={token}"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #f1f5f9; padding: 40px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #22c55e; font-size: 28px; margin: 0;">HeartMuLa Studio</h1>
            <p style="color: #94a3b8; margin-top: 8px;">Account Approved!</p>
        </div>
        <p>Hi <strong>{user_name}</strong>,</p>
        <p>Great news! Your HeartMuLa Studio account has been approved. Click the button below to activate your account and start creating music with AI.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{activate_url}" style="display: inline-block; background: #22c55e; color: #000; padding: 16px 40px; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 16px;">Activate My Account</a>
        </div>
        <p style="color: #94a3b8; font-size: 13px;">This link expires in 48 hours.</p>
        <p style="color: #64748b; font-size: 12px; text-align: center; margin-top: 30px;">HeartMuLa Studio - AI Music Creation</p>
    </div>
    """
    return subject, html


def email_login_code(user_name: str, code: str) -> tuple[str, str]:
    subject = f"HeartMuLa Studio - Your Login Code: {code}"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #f1f5f9; padding: 40px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #22c55e; font-size: 28px; margin: 0;">HeartMuLa Studio</h1>
            <p style="color: #94a3b8; margin-top: 8px;">Login Verification</p>
        </div>
        <p>Hi <strong>{user_name}</strong>,</p>
        <p>Use the following code to log in to HeartMuLa Studio:</p>
        <div style="text-align: center; margin: 30px 0;">
            <div style="display: inline-block; background: rgba(34,197,94,0.1); border: 2px solid #22c55e; border-radius: 12px; padding: 20px 40px; letter-spacing: 8px; font-size: 32px; font-weight: 700; font-family: monospace; color: #22c55e;">{code}</div>
        </div>
        <p style="color: #94a3b8; font-size: 13px; text-align: center;">This code expires in {CODE_EXPIRE_MINUTES} minutes.</p>
        <p style="color: #64748b; font-size: 12px; text-align: center; margin-top: 30px;">If you didn't request this code, you can safely ignore this email.</p>
    </div>
    """
    return subject, html


def email_registration_rejected(user_name: str) -> tuple[str, str]:
    subject = "HeartMuLa Studio - Registration Update"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #f1f5f9; padding: 40px; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #22c55e; font-size: 28px; margin: 0;">HeartMuLa Studio</h1>
        </div>
        <p>Hi <strong>{user_name}</strong>,</p>
        <p>Unfortunately, your registration request for HeartMuLa Studio was not approved at this time.</p>
        <p>If you believe this is a mistake, please contact the administrator.</p>
        <p style="color: #64748b; font-size: 12px; text-align: center; margin-top: 30px;">HeartMuLa Studio - AI Music Creation</p>
    </div>
    """
    return subject, html


# --- Auth Operations ---

class AuthService:
    def register_user(self, session: Session, name: str, email: str) -> dict:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            if existing.status == UserStatus.REJECTED:
                session.delete(existing)
                session.commit()
            else:
                return {"error": "email_exists", "message": "This email is already registered."}

        user = User(name=name, email=email, status=UserStatus.PENDING)
        session.add(user)
        session.flush()

        token = generate_token()
        code = VerificationCode(
            user_id=user.id,
            code=token,
            code_type=CodeType.ADMIN_APPROVAL,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(code)
        session.commit()

        subject, html = email_admin_approval(name, email, token)
        send_email_async(ADMIN_EMAIL, subject, html)

        return {"status": "pending", "message": "Registration submitted. Waiting for admin approval."}

    def approve_user(self, session: Session, token: str) -> dict:
        vc = session.exec(
            select(VerificationCode).where(
                VerificationCode.code == token,
                VerificationCode.code_type == CodeType.ADMIN_APPROVAL,
                VerificationCode.used == False,
            )
        ).first()

        if not vc:
            return {"error": "invalid_token", "message": "Invalid or expired approval token."}

        user = session.get(User, vc.user_id)
        if not user:
            return {"error": "user_not_found", "message": "User not found."}

        vc.used = True
        user.status = UserStatus.APPROVED

        activation_token = generate_token()
        activation_code = VerificationCode(
            user_id=user.id,
            code=activation_token,
            code_type=CodeType.USER_ACTIVATION,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        session.add(activation_code)
        session.commit()

        subject, html = email_user_activation(user.name, activation_token)
        send_email_async(user.email, subject, html)

        return {"status": "approved", "message": f"User {user.name} approved. Activation email sent."}

    def reject_user(self, session: Session, token: str) -> dict:
        vc = session.exec(
            select(VerificationCode).where(
                VerificationCode.code == token,
                VerificationCode.code_type == CodeType.ADMIN_APPROVAL,
                VerificationCode.used == False,
            )
        ).first()

        if not vc:
            return {"error": "invalid_token", "message": "Invalid or expired token."}

        user = session.get(User, vc.user_id)
        if not user:
            return {"error": "user_not_found", "message": "User not found."}

        vc.used = True
        user.status = UserStatus.REJECTED
        session.commit()

        subject, html = email_registration_rejected(user.name)
        send_email_async(user.email, subject, html)

        return {"status": "rejected", "message": f"User {user.name} rejected."}

    def activate_user(self, session: Session, token: str) -> dict:
        vc = session.exec(
            select(VerificationCode).where(
                VerificationCode.code == token,
                VerificationCode.code_type == CodeType.USER_ACTIVATION,
                VerificationCode.used == False,
            )
        ).first()

        if not vc:
            return {"error": "invalid_token", "message": "Invalid or expired activation link."}

        if vc.expires_at.replace(tzinfo=None) < datetime.utcnow():
            return {"error": "expired", "message": "Activation link has expired. Please contact admin."}

        user = session.get(User, vc.user_id)
        if not user:
            return {"error": "user_not_found", "message": "User not found."}

        vc.used = True
        user.status = UserStatus.ACTIVE
        session.commit()

        return {"status": "activated", "message": "Account activated! You can now log in."}

    def send_login_code(self, session: Session, email: str) -> dict:
        user = session.exec(select(User).where(User.email == email)).first()

        if not user:
            return {"error": "not_found", "message": "No account found with this email."}

        if user.status == UserStatus.PENDING:
            return {"error": "pending", "message": "Your account is waiting for admin approval."}

        if user.status == UserStatus.APPROVED:
            return {"error": "not_activated", "message": "Please check your email and activate your account first."}

        if user.status == UserStatus.REJECTED:
            return {"error": "rejected", "message": "Your registration was not approved."}

        if user.status != UserStatus.ACTIVE:
            return {"error": "inactive", "message": "Account is not active."}

        # Invalidate previous login codes
        old_codes = session.exec(
            select(VerificationCode).where(
                VerificationCode.user_id == user.id,
                VerificationCode.code_type == CodeType.LOGIN_CODE,
                VerificationCode.used == False,
            )
        ).all()
        for oc in old_codes:
            oc.used = True

        code = generate_code()
        vc = VerificationCode(
            user_id=user.id,
            code=code,
            code_type=CodeType.LOGIN_CODE,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRE_MINUTES),
        )
        session.add(vc)
        session.commit()

        subject, html = email_login_code(user.name, code)
        send_email_async(user.email, subject, html)

        return {"status": "sent", "message": "Verification code sent to your email.", "expires_in": CODE_EXPIRE_MINUTES * 60}

    def verify_login_code(self, session: Session, email: str, code: str) -> dict:
        user = session.exec(select(User).where(User.email == email)).first()

        if not user or user.status != UserStatus.ACTIVE:
            return {"error": "invalid", "message": "Invalid email or account not active."}

        vc = session.exec(
            select(VerificationCode).where(
                VerificationCode.user_id == user.id,
                VerificationCode.code == code,
                VerificationCode.code_type == CodeType.LOGIN_CODE,
                VerificationCode.used == False,
            )
        ).first()

        if not vc:
            return {"error": "invalid_code", "message": "Invalid verification code."}

        if vc.expires_at.replace(tzinfo=None) < datetime.utcnow():
            vc.used = True
            session.commit()
            return {"error": "expired", "message": "Code has expired. Please request a new one."}

        vc.used = True
        user.last_login = datetime.now(timezone.utc)
        session.commit()

        token = create_jwt(str(user.id), user.email)

        return {
            "status": "success",
            "token": token,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "is_admin": user.is_admin,
            },
        }


    def login_with_password(self, session: Session, email: str, password: str) -> dict:
        """Verify password, then send verification code (2FA). Token is NOT issued here."""
        user = session.exec(select(User).where(User.email == email)).first()

        if not user or not user.password_hash:
            return {"error": "invalid", "message": "Invalid email or password."}

        if not verify_password(password, user.password_hash):
            return {"error": "invalid", "message": "Invalid email or password."}

        if user.status != UserStatus.ACTIVE:
            return {"error": "inactive", "message": "Account is not active."}

        # Password correct — send verification code (same as passwordless flow)
        code = generate_code()
        vc = VerificationCode(
            user_id=user.id,
            code=code,
            code_type=CodeType.LOGIN_CODE,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRE_MINUTES),
        )
        session.add(vc)
        session.commit()

        subject, html = email_login_code(user.name, code)
        send_email_async(user.email, subject, html)

        return {"status": "sent", "message": "Password verified. Verification code sent to your email.", "expires_in": CODE_EXPIRE_MINUTES * 60}


def seed_super_admin(session: Session) -> None:
    existing = session.exec(select(User).where(User.email == SUPER_ADMIN_EMAIL)).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
        if not existing.password_hash:
            existing.password_hash = hash_password(SUPER_ADMIN_PASSWORD)
        if existing.status != UserStatus.ACTIVE:
            existing.status = UserStatus.ACTIVE
        session.commit()
        print(f"[Auth] Super admin updated: {SUPER_ADMIN_EMAIL}")
        return

    admin = User(
        name=SUPER_ADMIN_NAME,
        email=SUPER_ADMIN_EMAIL,
        password_hash=hash_password(SUPER_ADMIN_PASSWORD),
        is_admin=True,
        status=UserStatus.ACTIVE,
    )
    session.add(admin)
    session.commit()
    print(f"[Auth] Super admin created: {SUPER_ADMIN_EMAIL}")


auth_service = AuthService()
