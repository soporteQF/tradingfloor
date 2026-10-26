"""Chief of Staff API endpoints for Chief UI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from agents.chief import ChiefOfStaff, ChiefCommand
from agents.guardian import GuardianAgent
from orchestration.event_bus import EventBus
from knowledge_graph.client import KnowledgeGraph

router = APIRouter(prefix="/api/chief", tags=["chief"])

# Global references (set by main app)
chief_instance: Optional[ChiefOfStaff] = None
guardian_instance: Optional[GuardianAgent] = None


def set_chief_instance(chief: ChiefOfStaff, guardian: GuardianAgent):
    global chief_instance, guardian_instance
    chief_instance = chief
    guardian_instance = guardian


class CommandRequest(BaseModel):
    type: str
    strategy_id: Optional[str] = None
    target_state: Optional[str] = None
    reason: str = ""
    user: str = "operator"


@router.get("/status")
async def get_status():
    """Get full Chief status for UI."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    return chief_instance.get_status()


@router.post("/command")
async def send_command(cmd: CommandRequest):
    """Send command to Chief."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    
    chief_cmd = ChiefCommand(
        type=cmd.type,
        strategy_id=cmd.strategy_id,
        target_state=cmd.target_state,
        reason=cmd.reason,
        user=cmd.user,
    )
    chief_instance.send_command(chief_cmd)
    return {"status": "accepted", "command": cmd.type}


@router.get("/guardian/status")
async def get_guardian_status():
    """Get Guardian status."""
    if not guardian_instance:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    return guardian_instance.get_status()


@router.post("/guardian/kill-switch")
async def activate_kill_switch(reason: str = "Manual via API"):
    """Activate global kill switch."""
    if not guardian_instance:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    guardian_instance.activate_kill_switch(reason)
    return {"status": "activated", "reason": reason}


@router.post("/guardian/override")
async def override_guard(strategy_id: str, reason: str = "Manual override"):
    """Override guard for a strategy."""
    if not guardian_instance:
        raise HTTPException(status_code=503, detail="Guardian not initialized")
    guardian_instance.override_guard(strategy_id, reason)
    return {"status": "overridden", "strategy_id": strategy_id}


@router.get("/nightly/status")
async def get_nightly_status():
    """Get nightly loop status."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    status = chief_instance.get_status()
    return status.get("nightly", {})


@router.post("/nightly/run")
async def run_nightly_now():
    """Trigger nightly loop immediately."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    chief_instance.send_command(ChiefCommand(type="run_nightly_now", reason="Manual via API"))
    return {"status": "triggered"}


@router.post("/nightly/pause")
async def pause_nightly():
    """Pause nightly loop."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    chief_instance.send_command(ChiefCommand(type="pause_loop"))
    return {"status": "paused"}


@router.post("/nightly/resume")
async def resume_nightly():
    """Resume nightly loop."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    chief_instance.send_command(ChiefCommand(type="resume_loop"))
    return {"status": "resumed"}


@router.get("/strategies")
async def get_paper_strategies():
    """Get all paper trading strategies."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    status = chief_instance.get_status()
    return status.get("paper_strategies", {})


@router.post("/strategies/{strategy_id}/promote")
async def promote_strategy(strategy_id: str, reason: str = "Promoted by Chief"):
    """Promote strategy to paper trading."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    chief_instance.send_command(ChiefCommand(type="promote", strategy_id=strategy_id, reason=reason))
    return {"status": "promoted", "strategy_id": strategy_id}


@router.post("/strategies/{strategy_id}/retire")
async def retire_strategy(strategy_id: str, reason: str = "Retired by Chief"):
    """Retire strategy."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    chief_instance.send_command(ChiefCommand(type="retire", strategy_id=strategy_id, reason=reason))
    return {"status": "retired", "strategy_id": strategy_id}


@router.get("/alerts")
async def get_guardian_alerts(limit: int = 50):
    """Get recent guardian alerts."""
    if not chief_instance:
        raise HTTPException(status_code=503, detail="Chief not initialized")
    status = chief_instance.get_status()
    alerts = status.get("guardian_alerts", [])
    return alerts[-limit:]


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "chief_initialized": chief_instance is not None,
        "guardian_initialized": guardian_instance is not None,
    }