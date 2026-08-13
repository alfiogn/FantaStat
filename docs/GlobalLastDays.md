# Global Last N Days

`N` is calendar days, not matchdays.

Metrics recomputed in the window:

- `window_QI`: first player quotation in the window, fallback to season QI
- `window_QA`: last player quotation in the window, fallback to season QA
- `window_quotation_delta`
- `window_FV`: average fantavoto
- `window_MV`: average voto
- `window_FVM`: current FVM from quotation snapshot
- `window_goals`
- `window_assists`

FVM is not historical in the current scraper output, so the app uses the current quotation snapshot.
