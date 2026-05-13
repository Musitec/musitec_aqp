from app.modules.contacts.send_email import send_pin_email
import random
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Response, Request
from app.core.config import settings
from app.modules.auth import repository
from app.modules.orders import repository as orders_repository
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    set_refresh_cookie,
    decode_token,
    set_access_cookie,
    clear_refresh_cookie,
    hash_pin,
    verify_pin_hash
)

MAX_PIN_ATTEMPTS = 5
MAX_PIN_REQUESTS = 5
PIN_REQUEST_WINDOW = timedelta(minutes=1)
BLOCK_TIME = timedelta(hours=1)
PIN_EXPIRE_MINUTES = 10
MAX_SESSIONS = 5

async def handle_user_block_state(user: dict):
    now = datetime.now(timezone.utc)
    if user.get("blocked_until"):
        blocked_until = user["blocked_until"]
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)
        if blocked_until <= now:
            await repository.update_user_block_status(
                email=user["email"],
                is_blocked=False,
                now=now,
                blocked_until=None
            )
            await repository.deactivate_all_sessions(user["id"])
            user["is_blocked"] = False
            user["blocked_until"] = None
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Cuenta temporalmente bloqueada"
            )
    if user.get("is_blocked"):
        await repository.deactivate_all_sessions(user["id"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado"
        )

async def attach_guest_orders_to_user(user_id: str, email: str):
    exists = await orders_repository.exists_guest_orders(email)
    if not exists:
        return 0
    return await orders_repository.attach_orders_to_user(user_id, email)

def to_utc_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def generate_pin() -> str:
    return f"{random.randint(0, 999999):06d}"

async def register_user(name: str, email: str, request:Request, phone: str, date: int, sex: str):
    email = email.lower().strip()
    existing = await repository.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El correo ya está registrado")
    role="moderator" if email==settings.EMAIL_USER else "client"
    user = await repository.create_user(name, email, phone, date, sex, role)
    pin = generate_pin()
    pin_hash = hash_pin(pin)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=PIN_EXPIRE_MINUTES)
    now = datetime.now(tz=timezone.utc)
    ip = request.client.host if request.client else None
    await repository.upsert_email_pin(user["id"], pin_hash, "verify_email", expires_at, 1, now, ip)
    await send_pin_email(
        name=name,
        email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
        pin=pin
    )
    return {"message": "Usuario creado. Revisa tu correo para el PIN."}

async def resend_pin(email: str, request: Request):
    email = email.lower().strip()
    user = await repository.get_user_by_email(email)
    now = datetime.now(tz=timezone.utc)
    ip = request.client.host if request.client else None
    if not user or user.get("is_verified"):
        return {"message": "Si el correo existe, se ha enviado un PIN"}
    pin = generate_pin()
    pin_hash = hash_pin(pin)
    expires_at = now + timedelta(minutes=PIN_EXPIRE_MINUTES)
    record = await repository.get_active_pin_by_purpose(user["id"], "verify_email")
    request_count = 1
    if record:
        blocked_until = record.get("blocked_until")
        if blocked_until:
            if blocked_until.tzinfo is None:
                blocked_until = blocked_until.replace(tzinfo=timezone.utc)
            if blocked_until > now:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Has sido bloqueado temporalmente. Intenta más tarde."
                )
        last_requested = record.get("last_requested_at")
        if last_requested:
            if last_requested.tzinfo is None:
                last_requested = last_requested.replace(tzinfo=timezone.utc)
            if now - last_requested < PIN_REQUEST_WINDOW:
                request_count = record.get("request_count", 0) + 1
        if request_count > MAX_PIN_REQUESTS:
            blocked_until = now + BLOCK_TIME
            await repository.block_pin_requests(user["id"], "verify_email", blocked_until)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta más tarde."
            )
    count = await repository.count_recent_pin_requests_by_ip(ip, window_minutes=5)
    if count > 20:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes desde tu IP"
        )
    await repository.upsert_email_pin(
        user_id=user["id"],
        pin_hash=pin_hash,
        purpose="verify_email",
        expires_at=expires_at,
        request_count=request_count,
        last_requested_at=now,
        ip_address=ip
    )
    await send_pin_email(name=user["name"], email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email, pin=pin)
    return {"message": "Si el correo existe, se ha enviado un PIN"}

async def verify_pin(email: str, pin: str, request: Request):
    email = email.lower().strip()
    user = await repository.get_user_by_email(email)
    now = datetime.now(tz=timezone.utc)
    ip = request.client.host if request.client else None
    if not user:
        await repository.log_security_event(
            user_id=None,
            email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
            ip=ip,
            event_type="PIN_VERIFY_FAILED_NO_USER"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    record = await repository.get_active_pin_by_purpose(user["id"], "verify_email")
    if not record:
        await repository.log_security_event(
            user["id"],
            settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
            ip,
            "PIN_VERIFY_FAILED_NO_ACTIVE_PIN",
            {"purpose": "verify_email"}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await repository.invalidate_pin(user["id"], purpose="verify_email")
        await repository.log_security_event(
            user["id"],
            settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
            ip,
            "PIN_EXPIRED",
            {"purpose": "verify_email"}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    blocked_until = record.get("blocked_until")
    if blocked_until:
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)
        if blocked_until > now:
            await repository.log_security_event(
                user["id"],
                settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
                ip,
                "PIN_VERIFY_BLOCKED",
                {"purpose": "verify_email"}
            )
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Bloqueado temporalmente")
    if not verify_pin_hash(pin, record["pin_hash"]):
        await repository.increment_pin_attempts(user["id"], purpose="verify_email")
        attempts = (record.get("attempts") or 0) + 1
        if attempts >= MAX_PIN_ATTEMPTS:
            blocked_until = now + BLOCK_TIME
            await repository.block_pin_requests(user["id"], purpose="verify_email", blocked_until=blocked_until)
            await repository.invalidate_pin(user["id"], purpose="verify_email")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    await repository.invalidate_pin_success(user["id"], purpose="verify_email")
    await repository.set_user_verified(user["id"])
    await repository.log_security_event(
        user_id=user["id"],
        email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
        ip=ip,
        event_type="EMAIL_VERIFIED"
    )
    return {"message": "Correo verificado correctamente"}

async def set_password(response: Response, email: str, password: str, confirm_password: str, request: Request):
    email = email.lower().strip()
    if password != confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    user = await repository.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    if not user["is_verified"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    if user["is_blocked"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    if user.get("password_hash"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales incorrectas")
    password_hash = hash_password(password)
    await repository.set_user_password(user["id"], password_hash)
    await attach_guest_orders_to_user(user_id=str(user["id"]),email=email)
    ip=request.client.host if request.client else None
    session = await repository.create_session(
        user_id=user["id"],
        refresh_hash="PENDING",
        user_agent=request.headers.get("user-agent"),
        ip=ip
    )
    refresh_token = create_refresh_token(session["_id"])
    refresh_hash = hash_token(refresh_token)
    await repository.update_session_refresh_hash(session["_id"], refresh_hash)
    access_token = create_access_token(user["id"], session["_id"])
    set_refresh_cookie(response, refresh_token)
    set_access_cookie(response, access_token)
    return {"message": "Inicio de sesión exitoso"}

async def login(response: Response, email: str, password: str, request: Request):
    email = email.lower().strip()
    ip = request.client.host if request.client else None
    user = await repository.get_user_by_email(email)
    if not user:
        await repository.log_security_event(
            user_id=None,
            email=email,
            ip=ip,
            event_type="LOGIN_FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas"
        )
    now = datetime.now(tz=timezone.utc)
    if user.get("is_blocked"):
        blocked_until = user.get("blocked_until")
        if blocked_until:
            if now >= blocked_until:
                await repository.update_user_block_status(
                    email=user["email"],
                    is_blocked=False,
                    now=now,
                    blocked_until=None
                )
                await repository.deactivate_all_sessions(user["id"])
                await repository.log_security_event(
                    user_id=user["id"],
                    email=email,
                    ip=ip,
                    event_type="AUTO_UNBLOCK"
                )
                user["is_blocked"] = False
                user["blocked_until"] = None
            else:
                await repository.deactivate_all_sessions(user["id"])
                await repository.log_security_event(
                    user_id=user["id"],
                    email=email,
                    ip=ip,
                    event_type="LOGIN_BLOCKED"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Cuenta bloqueada hasta {blocked_until.isoformat()}"
                )
        else:
            await repository.deactivate_all_sessions(user["id"])
            await repository.log_security_event(
                user_id=user["id"],
                email=email,
                ip=ip,
                event_type="LOGIN_BLOCKED"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta bloqueada"
            )
    if not user["is_verified"] or not user.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas"
        )
    if not verify_password(password, user["password_hash"]):
        attempts = await repository.increment_failed_login(user["id"])
        blocked_until = None
        if attempts >= 15:
            blocked_until = now + timedelta(hours=24)
        elif attempts >= 10:
            blocked_until = now + timedelta(minutes=30)
        elif attempts >= 5:
            blocked_until = now + timedelta(minutes=5)
        if blocked_until:
            await repository.block_user_until(user["id"], blocked_until)
        await repository.log_security_event(
            user_id=user["id"],
            email=email,
            ip=ip,
            event_type="LOGIN_FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas"
        )
    await repository.reset_failed_logins(user["id"])
    active_sessions = await repository.count_active_sessions(user["id"])
    if active_sessions >= MAX_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demasiadas sesiones activas"
        )
    await attach_guest_orders_to_user(
        user_id=str(user["id"]),
        email=email
    )
    session = await repository.create_session(
        user_id=user["id"],
        refresh_hash="PENDING",
        user_agent=request.headers.get("user-agent"),
        ip=ip
    )
    refresh_token = create_refresh_token(session["_id"])
    refresh_hash = hash_token(refresh_token)
    await repository.update_session_refresh_hash(
        session["_id"],
        refresh_hash
    )
    access_token = create_access_token(user["id"], session["_id"])
    set_refresh_cookie(response, refresh_token)
    set_access_cookie(response, access_token)
    await repository.log_security_event(
        user_id=user["id"],
        email=email,
        ip=ip,
        event_type="LOGIN_SUCCESS"
    )
    return {"message": "Inicio de sesión exitoso"}

async def refresh_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales inválidas")
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        if payload.get("sid"):
            await repository.deactivate_session(payload["sid"])
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales inválidas")
    session_id = payload["sid"]
    session = await repository.get_session_by_id(session_id)
    if not session or not session.get("is_active"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales inválidas")
    if hash_token(refresh_token) != session["refresh_token_hash"]:
        await repository.deactivate_session(session_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales inválidas")
    new_refresh_token = create_refresh_token(str(session_id))
    new_refresh_hash = hash_token(new_refresh_token)
    await repository.update_session_refresh_hash(session_id, new_refresh_hash)
    access_token = create_access_token(
        str(session["user_id"]),
        str(session["id"])
    )
    set_refresh_cookie(response, new_refresh_token)
    set_access_cookie(response, access_token)
    return {
        "message": "Token actualizado correctamente"
    }

async def logout_current(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return {"message": "Sesión cerrada"}
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise Exception()
    except:
        clear_refresh_cookie(response)
        return {"message": "Sesión cerrada"}
    session_id = payload["sid"]
    await repository.deactivate_session(session_id)
    clear_refresh_cookie(response)
    return {"message": "Sesión cerrada correctamente"}

async def logout_all(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        clear_refresh_cookie(response)
        return {"message": "Sesiones cerradas"}
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise Exception()
    except:
        clear_refresh_cookie(response)
        return {"message": "Sesiones cerradas"}
    session_id = payload["sid"]
    session = await repository.get_session_by_id(session_id)
    if session:
        await repository.deactivate_all_sessions(session["user_id"])
    clear_refresh_cookie(response)
    return {"message": "Todas las sesiones cerradas"}

async def start_password_reset(email: str, request: Request):
    email = email.lower().strip()
    user = await repository.get_user_by_email(email)
    ip = request.client.host if request.client else None
    if user:
        await handle_user_block_state(user)
        pin = generate_pin()
        pin_hash = hash_pin(pin)
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=PIN_EXPIRE_MINUTES)
        now = datetime.now(tz=timezone.utc)
        await repository.upsert_email_pin(
            user_id=user["id"],
            pin_hash=pin_hash,
            purpose="reset_password",
            expires_at=expires_at,
            request_count=1,
            last_requested_at=now,
            ip_address=ip
        )
        await send_pin_email(
            name=user["name"],
            email=settings.PERSONAL_EMAIL if email == settings.EMAIL_USER else email,
            pin=pin
        )
        await repository.log_security_event(
            user_id=user["id"],
            email=settings.PERSONAL_EMAIL if email == settings.EMAIL_USER else email,
            ip=ip,
            event_type="PASSWORD_RESET_REQUEST"
        )
    return {"message": "Si el correo existe, se ha enviado un PIN"}

async def resend_password_reset_pin(email: str, request: Request):
    email = email.lower().strip()
    user = await repository.get_user_by_email(email)
    now = datetime.now(tz=timezone.utc)
    ip = request.client.host if request.client else None
    if not user:
        return {"message": "Si el correo existe, se ha enviado un PIN"}
    await handle_user_block_state(user)
    pin = generate_pin()
    pin_hash = hash_pin(pin)
    expires_at = now + timedelta(minutes=PIN_EXPIRE_MINUTES)
    record = await repository.get_active_pin_by_purpose(user["id"], "reset_password")
    request_count = 1
    if record:
        blocked_until = record.get("blocked_until")
        if blocked_until:
            if blocked_until.tzinfo is None:
                blocked_until = blocked_until.replace(tzinfo=timezone.utc)
            if blocked_until > now:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Has sido bloqueado temporalmente. Intenta más tarde"
                )
        last_requested = record.get("last_requested_at")
        if last_requested:
            if last_requested.tzinfo is None:
                last_requested = last_requested.replace(tzinfo=timezone.utc)
            if now - last_requested < PIN_REQUEST_WINDOW:
                request_count = record.get("request_count", 0) + 1
        if request_count > MAX_PIN_REQUESTS:
            blocked_until = now + BLOCK_TIME
            await repository.block_pin_requests(user["id"], blocked_until, purpose="reset_password")
            await repository.log_security_event(
                user_id=user["id"], email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email, ip=ip,
                event_type="PIN_BLOCKED", metadata={"purpose": "reset_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes"
            )
    count = await repository.count_recent_pin_requests_by_ip(ip, window_minutes=5)
    if count > 20:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes desde tu IP"
        )
    await repository.upsert_email_pin(
        user_id=user["id"],
        pin_hash=pin_hash,
        purpose="reset_password",
        expires_at=expires_at,
        request_count=request_count,
        last_requested_at=now,
        ip_address=ip
    )
    await send_pin_email(name=user["name"], email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email, pin=pin)
    return {"message": "Si el correo existe, se ha enviado un PIN"}

async def verify_password_reset_pin(email: str, pin: str, request: Request):
    email = email.lower().strip()
    now = datetime.now(tz=timezone.utc)
    user = await repository.get_user_by_email(email)
    ip = request.client.host if request.client else None
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN incorrecto")
    await handle_user_block_state(user)
    record = await repository.get_active_pin_by_purpose(user["id"], "reset_password")
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN inválido o expirado")
    expires_at = to_utc_aware(record.get("expires_at"))
    blocked_until = to_utc_aware(record.get("blocked_until"))
    if expires_at and expires_at < now:
        await repository.invalidate_pin(user["id"], purpose="reset_password")
        await repository.log_security_event(
            user_id=user["id"],
            email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
            ip=ip,
            event_type="PIN_EXPIRED",
            metadata={"purpose": "reset_password"}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN expirado")
    if blocked_until and blocked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has sido bloqueado temporalmente. Intenta más tarde"
        )
    if not verify_pin_hash(pin, record["pin_hash"]):
        await repository.increment_pin_attempts(user["id"], purpose="reset_password")
        attempts = (record.get("attempts") or 0) + 1
        await repository.log_security_event(
            user_id=user["id"],
            email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
            ip=ip,
            event_type="PIN_FAILED",
            metadata={"purpose": "reset_password", "attempts": attempts}
        )
        if attempts >= MAX_PIN_ATTEMPTS:
            blocked_until = now + BLOCK_TIME
            await repository.block_pin_requests(user["id"], "reset_password", blocked_until)
            await repository.log_security_event(
                user_id=user["id"],
                email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
                ip=ip,
                event_type="PIN_BLOCKED",
                metadata={"purpose": "reset_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Has sido bloqueado temporalmente."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN incorrecto")
    await repository.mark_pin_verified(user["id"], "reset_password")
    await repository.log_security_event(
        user_id=user["id"],
        email=settings.PERSONAL_EMAIL if email==settings.EMAIL_USER else email,
        ip=ip,
        event_type="PIN_VERIFIED",
        metadata={"purpose": "reset_password"}
    )
    return {"message": "PIN válido"}

async def confirm_password_reset(
    email: str,
    new_password: str,
    confirm_password: str,
    response: Response,
    request: Request
):
    email = email.lower().strip()
    ip = request.client.host if request.client else None
    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas"
        )
    user = await repository.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales incorrectas"
        )
    now = datetime.now(timezone.utc)
    if user.get("is_blocked"):
        blocked_until = user.get("blocked_until")
        if blocked_until:
            if now >= blocked_until:
                await repository.update_user_block_status(
                    email=user["email"],
                    is_blocked=False,
                    now=now,
                    blocked_until=None
                )
                user["is_blocked"] = False
                user["blocked_until"] = None
            else:
                await repository.deactivate_all_sessions(user["id"])
                await repository.log_security_event(
                    user_id=user["id"],
                    email=email,
                    ip=ip,
                    event_type="RESET_BLOCKED"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cuenta bloqueada hasta {blocked_until.isoformat()}"
                )
        else:
            await repository.deactivate_all_sessions(user["id"])

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta bloqueada"
            )
    record = await repository.get_verified_pin_by_purpose(
        user["id"],
        "reset_password"
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN no validado o expirado"
        )
    password_hash = hash_password(new_password)
    await repository.invalidate_pin_success(
        user["id"],
        purpose="reset_password"
    )
    await repository.set_user_password(
        user["id"],
        password_hash
    )
    await repository.deactivate_all_sessions(user["id"])
    await repository.log_security_event(
        user_id=user["id"],
        email=email,
        ip=ip,
        event_type="PASSWORD_CHANGED"
    )
    await attach_guest_orders_to_user(
        user_id=str(user["id"]),
        email=email
    )
    session = await repository.create_session(
        user_id=user["id"],
        refresh_hash="PENDING",
        user_agent=request.headers.get("user-agent"),
        ip=ip,
    )
    refresh_token = create_refresh_token(str(session["_id"]))
    refresh_hash = hash_token(refresh_token)
    await repository.update_session_refresh_hash(
        session["_id"],
        refresh_hash
    )
    access_token = create_access_token(
        str(session["user_id"]),
        str(session["_id"])
    )
    set_refresh_cookie(response, refresh_token)
    set_access_cookie(response, access_token)
    return {
        "message": "Cambio de contraseña completado"
    }