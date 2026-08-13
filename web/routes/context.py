from __future__ import annotations

from repositories import CalendarRepository, Database, PlayerRepository, QuotationRepository, TeamRepository
from services import CurrentSeasonService, TimelineService, TimeWindowService, WindowSnapshotService


database = Database()
quotation_repo = QuotationRepository(database)
player_repo = PlayerRepository(database)
calendar_repo = CalendarRepository(database)
team_repo = TeamRepository(database)

timeline_service = TimelineService()
current_season_service = CurrentSeasonService(calendar_repo, player_repo, quotation_repo)
time_window_service = TimeWindowService(calendar_repo, player_repo, quotation_repo)

window_snapshot_service = WindowSnapshotService(
    quotation_repo=quotation_repo,
    player_repo=player_repo,
    time_window_service=time_window_service,
    timeline_service=timeline_service,
    ttl_seconds=900,
    max_entries=32,
)
