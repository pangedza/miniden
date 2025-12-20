"""CRUD для бот-узлов (экраны/сообщения)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotNode
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])


ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


@router.get("/nodes")
async def list_nodes(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    nodes = (
        db.query(BotNode)
        .order_by(BotNode.updated_at.desc().nullslast(), BotNode.id.desc())
        .all()
    )

    return TEMPLATES.TemplateResponse(
        "adminbot_nodes_list.html",
        {
            "request": request,
            "user": user,
            "nodes": nodes,
        },
    )


@router.get("/nodes/new")
async def new_node_form(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    return TEMPLATES.TemplateResponse(
        "adminbot_node_edit.html",
        {
            "request": request,
            "user": user,
            "node": None,
            "error": None,
        },
    )


@router.post("/nodes/new")
async def create_node(
    request: Request,
    code: str = Form(...),
    title: str = Form(...),
    message_text: str = Form(...),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    code = (code or "").strip()
    existing = db.query(BotNode).filter(BotNode.code == code).first()
    if existing:
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": None,
                "error": "Код узла уже используется",
            },
            status_code=400,
        )

    db.add(
        BotNode(
            code=code,
            title=title,
            message_text=message_text,
            parse_mode=parse_mode or "HTML",
            image_url=image_url or None,
            is_enabled=is_enabled,
        )
    )
    db.commit()

    return RedirectResponse(url="/adminbot/nodes", status_code=303)


@router.get("/nodes/{node_id}/edit")
async def edit_node_form(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_node_edit.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "error": None,
        },
    )


@router.post("/nodes/{node_id}/edit")
async def edit_node(
    request: Request,
    node_id: int,
    title: str = Form(...),
    message_text: str = Form(...),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    node.title = title
    node.message_text = message_text
    node.parse_mode = parse_mode or "HTML"
    node.image_url = image_url or None
    node.is_enabled = is_enabled

    db.add(node)
    db.commit()

    return RedirectResponse(url="/adminbot/nodes", status_code=303)
