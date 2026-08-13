from __future__ import annotations

from repositories import (
    CalendarRepository,
    Database,
    PlayerRepository,
    QuotationRepository,
    TeamRepository,
)
from services import ComparisonService, CurrentSeasonService, TimelineService, SummaryService
from services.time_window import TimeWindowService

database = Database()
quotation_repo = QuotationRepository(database)
player_repo = PlayerRepository(database)
calendar_repo = CalendarRepository(database)
team_repo = TeamRepository(database)

timeline_service = TimelineService()
time_window_service = TimeWindowService(calendar_repo, player_repo, quotation_repo)
summary_service = SummaryService()
comparison_service = ComparisonService(player_repo)
current_season_service = CurrentSeasonService(calendar_repo, player_repo, quotation_repo)
