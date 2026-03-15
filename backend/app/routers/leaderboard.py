"""Public leaderboard endpoints for model reliability ranking."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import BenchmarkRun, BenchmarkStatus
from app.schemas import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("/models", response_model=list[LeaderboardEntry])
async def model_leaderboard(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    rows = await db.execute(
        select(BenchmarkRun)
        .where(BenchmarkRun.status == BenchmarkStatus.COMPLETED)
        .order_by(BenchmarkRun.created_at.desc())
        .limit(5000)
    )
    runs = rows.scalars().all()

    grouped: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "reliability": [],
            "hallucination": [],
            "miss": [],
            "latency": [],
            "count": 0,
        }
    )
    for run in runs:
        key = (run.ai_provider, run.ai_model)
        grouped[key]["count"] += 1
        grouped[key]["reliability"].append(run.avg_reliability_score or 0.0)
        grouped[key]["hallucination"].append(run.avg_hallucination_rate or 0.0)
        grouped[key]["miss"].append(run.avg_miss_rate or 0.0)
        grouped[key]["latency"].append(run.avg_latency_ms or 0.0)

    ranked = []
    for (provider, model_name), metrics in grouped.items():
        n = max(metrics["count"], 1)
        ranked.append(
            {
                "provider": provider,
                "model_name": model_name,
                "reliability_score": sum(metrics["reliability"]) / n,
                "hallucination_rate": sum(metrics["hallucination"]) / n,
                "miss_rate": sum(metrics["miss"]) / n,
                "average_latency_ms": sum(metrics["latency"]) / n,
                "benchmark_runs": metrics["count"],
            }
        )

    ranked.sort(key=lambda x: x["reliability_score"], reverse=True)
    output: list[LeaderboardEntry] = []
    for idx, item in enumerate(ranked[:limit], start=1):
        output.append(LeaderboardEntry(rank=idx, **item))
    return output
