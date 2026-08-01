from fastapi import APIRouter

from admin.common import (
    DATABASE_PATH,
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    active_count,
    campaign_count,
    create_session_token,
    dashboard_daily_series,
    dashboard_metrics,
    dashboard_recent_activity,
    esc,
    is_authenticated,
    notification_count,
    page_layout,
    panel_password,
    read_form,
    require_auth,
    session_secret,
    user_count,
    valid_session_token,
)
from admin.analytics import router as analytics_router
from admin.auth import router as auth_router
from admin.campaigns import public_router as campaigns_public_router
from admin.campaigns import router as campaigns_router
from admin.dashboard import router as dashboard_router
from admin.features import router as features_router
from admin.notifications import public_router as notifications_public_router
from admin.notifications import router as notifications_router
from admin.settings import router as settings_router
from admin.users_router import router as users_router

router = APIRouter(tags=["admin-panel"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(users_router)
router.include_router(campaigns_router)
router.include_router(notifications_router)
router.include_router(notifications_public_router)
router.include_router(analytics_router)
router.include_router(features_router)
router.include_router(settings_router)
router.include_router(campaigns_public_router)
