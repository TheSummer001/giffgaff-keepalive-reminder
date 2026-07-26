from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import Settings
from .database import Database
from .notifications import NotificationService, simple_html
from .reminders import age_days, deadline, stage_for_days, suggested_action_date
from .scheduler import ReminderScheduler
from .security import InvalidToken, create_token, verify_token


BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
settings = Settings.from_env()
database = Database(settings.database_path)
notifications = NotificationService(settings)
scheduler = ReminderScheduler(settings, database, notifications)


def now_local() -> datetime:
    return datetime.now(settings.timezone)


def admin_is_authenticated(request: Request) -> bool:
    token = request.cookies.get("admin_session")
    if not token:
        return False
    try:
        verify_token(settings.app_secret, token, "admin")
    except InvalidToken:
        return False
    return True


def require_admin(request: Request) -> None:
    if not admin_is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def require_current_cycle_token(token: str, purpose: str) -> None:
    try:
        payload = verify_token(settings.app_secret, token, purpose)
    except InvalidToken as exc:
        raise HTTPException(400, f"链接无效：{exc}") from exc
    current_cycle = database.get_state()["cycle_started_at"]
    if payload.get("cycle") != current_cycle:
        raise HTTPException(400, "该链接属于已经完成的提醒周期")


def parse_recent_date(value: str, today: date) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, "日期格式无效") from exc
    if parsed > today or parsed < today - timedelta(days=7):
        raise HTTPException(400, "只能选择今天或最近七天内的日期")
    return parsed


def view_context(request: Request) -> dict[str, object]:
    state = database.get_state()
    last_sms_date = date.fromisoformat(str(state["last_sms_date"]))
    today = now_local().date()
    days = age_days(last_sms_date, today)
    stage = stage_for_days(days)
    return {
        "request": request,
        "app_name": settings.app_name,
        "last_sms_date": last_sms_date,
        "today": today,
        "min_confirm_date": today - timedelta(days=7),
        "days_elapsed": days,
        "suggested_date": suggested_action_date(last_sms_date),
        "deadline_date": deadline(last_sms_date),
        "stage_label": stage.label if stage else "正常",
        "snoozed_until": state["snoozed_until"],
        "channels": notifications.enabled_channels,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    database.initialize(
        date.fromisoformat(settings.initial_last_sms_date), now_local()
    )
    task = asyncio.create_task(scheduler.run())
    yield
    scheduler.stop()
    await task


app = FastAPI(title="giffgaff Reminder", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "time": now_local().isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not admin_is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    context = view_context(request)
    context["events"] = database.recent_events()
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "app_name": settings.app_name, "error": None},
    )


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, password: str = Form(...)):
    if not hmac.compare_digest(password, settings.admin_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "error": "密码错误",
            },
            status_code=401,
        )
    token = create_token(
        settings.app_secret,
        "admin",
        expires_in_seconds=7 * 24 * 60 * 60,
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


@app.get("/confirm/{token}", response_class=HTMLResponse)
async def confirm_page(request: Request, token: str):
    require_current_cycle_token(token, "confirm")
    context = view_context(request)
    context["token"] = token
    return templates.TemplateResponse(request, "confirm.html", context)


@app.post("/confirm/{token}", response_class=HTMLResponse)
async def confirm_sms(
    request: Request,
    token: str,
    sent_date: str = Form(...),
):
    require_current_cycle_token(token, "confirm")
    now = now_local()
    parsed_date = parse_recent_date(sent_date, now.date())
    database.mark_sms_sent(parsed_date, now)

    next_date = suggested_action_date(parsed_date)
    results = await notifications.send_all(
        "giffgaff 保号操作已确认",
        simple_html(
            "已记录本次短信",
            f"短信日期：{parsed_date.isoformat()}；"
            f"下一次建议操作：{next_date.isoformat()}。",
        ),
    )
    for result in results:
        database.add_event(
            event_type="confirmation_receipt",
            channel=result.channel,
            stage=None,
            status="success" if result.success else "failed",
            message=result.detail,
            now=now,
        )
    return templates.TemplateResponse(
        request,
        "done.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "sent_date": parsed_date,
            "next_date": next_date,
            "deadline_date": deadline(parsed_date),
        },
    )


@app.get("/snooze/{token}", response_class=HTMLResponse)
async def snooze_page(request: Request, token: str):
    require_current_cycle_token(token, "snooze")
    return templates.TemplateResponse(
        request,
        "snooze_confirm.html",
        {"request": request, "app_name": settings.app_name, "token": token},
    )


@app.post("/snooze/{token}", response_class=HTMLResponse)
async def snooze(request: Request, token: str):
    require_current_cycle_token(token, "snooze")
    now = now_local()
    until = now + timedelta(hours=24)
    database.snooze(until, now)
    return templates.TemplateResponse(
        request,
        "snoozed.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "until": until,
        },
    )


@app.post("/admin/mark-sent")
async def admin_mark_sent(request: Request, sent_date: str = Form(...)):
    require_admin(request)
    now = now_local()
    database.mark_sms_sent(parse_recent_date(sent_date, now.date()), now)
    return RedirectResponse("/", status_code=303)


@app.post("/admin/test")
async def admin_test(request: Request):
    require_admin(request)
    now = now_local()
    test_url = f"{settings.public_base_url}/login"
    results = await notifications.send_all(
        "giffgaff 提醒服务测试",
        simple_html(
            "测试通知发送成功",
            f"服务时间：{now:%Y-%m-%d %H:%M}；管理入口：{test_url}",
        ),
    )
    for result in results:
        database.add_event(
            event_type="test",
            channel=result.channel,
            stage=None,
            status="success" if result.success else "failed",
            message=result.detail,
            now=now,
        )
    return RedirectResponse("/", status_code=303)
