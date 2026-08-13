# Add this to routes/context.py
from services.time_window import TimeWindowService

time_window_service = TimeWindowService(calendar_repo, player_repo, quotation_repo)
