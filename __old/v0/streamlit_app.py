from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
except Exception:
    AgGrid = None
    GridOptionsBuilder = None
    GridUpdateMode = None
    JsCode = None

from auction_service import AuctionError, AuctionService
from auction_store import AuctionStore


DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_AUCTIONS_DIR = Path("auctions")


# -----------------------------
# Cache loading
# -----------------------------

def _stats_path(cache_dir: Path, year: int) -> Path:
    return cache_dir / f"stats{year}.json"


def _quotazioni_path(cache_dir: Path, year: int) -> Path:
    return cache_dir / f"quotazioni{year}.csv"


def _payload_to_dataframe(payload: Mapping[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(payload.get("records", []))
    attrs = payload.get("attrs", {})
    if isinstance(attrs, Mapping):
        df.attrs.update(dict(attrs))
    return df


@st.cache_data(show_spinner=False)
def load_quotazioni(cache_dir: str, year: int) -> pd.DataFrame:
    path = _quotazioni_path(Path(cache_dir), year)
    if not path.exists():
        raise FileNotFoundError(f"Missing quotazioni cache: {path}")
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_stats(cache_dir: str, year: int) -> dict[str, pd.DataFrame]:
    path = _stats_path(Path(cache_dir), year)
    if not path.exists():
        raise FileNotFoundError(f"Missing stats cache: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    return {name: _payload_to_dataframe(data) for name, data in payload.items()}


def refresh_cache(year: int, cache_dir: Path, proxy: str | None, max_workers: int, verify: bool) -> None:
    from scraper_refactored import run

    proxies = {"http": proxy, "https": proxy} if proxy else None
    run(
        year,
        cache_dir=cache_dir,
        proxies=proxies,
        verify=verify,
        max_workers=max_workers,
        force=True,
    )
    st.cache_data.clear()


# -----------------------------
# Dashboard helpers
# -----------------------------

def player_summary_from_stats(name: str, df: pd.DataFrame) -> dict[str, Any]:
    attrs = df.attrs
    summary_stats = attrs.get("summary_stats", {}) or {}
    bridge = attrs.get("bridge", {}) or {}

    def summary_value(*keys: str) -> Any:
        for key in keys:
            rec = summary_stats.get(key)
            if isinstance(rec, Mapping) and rec.get("value") is not None:
                return rec.get("value")
        return None

    return {
        "nome": name,
        "player_name": attrs.get("player_name") or name,
        "team_detail": attrs.get("team"),
        "roles_detail": ", ".join(
            str(r.get("data_value") or r.get("title") or "")
            for r in attrs.get("roles", [])
            if isinstance(r, Mapping)
        ),
        "partite": len(df),
        "voto_mean": pd.to_numeric(df.get("voto"), errors="coerce").mean() if "voto" in df else None,
        "fantavoto_mean": pd.to_numeric(df.get("fantavoto"), errors="coerce").mean() if "fantavoto" in df else None,
        "goal": pd.to_numeric(df.get("scoredGoals"), errors="coerce").sum() if "scoredGoals" in df else None,
        "assist": pd.to_numeric(df.get("assists"), errors="coerce").sum() if "assists" in df else None,
        "yellow": pd.to_numeric(df.get("yellowCards"), errors="coerce").sum() if "yellowCards" in df else None,
        "red": pd.to_numeric(df.get("redCards"), errors="coerce").sum() if "redCards" in df else None,
        "summary_mv": summary_value("MV", "Media Voto", "Media voto"),
        "summary_fm": summary_value("FM", "Fanta Media", "Fantamedia"),
        "bridge_player_id": bridge.get("playerId"),
    }


def build_players_table(quotazioni: pd.DataFrame, stats: dict[str, pd.DataFrame]) -> pd.DataFrame:
    stat_rows = [player_summary_from_stats(name, df) for name, df in stats.items()]
    stats_df = pd.DataFrame(stat_rows)
    out = quotazioni.copy()
    if "nome" in out.columns and not stats_df.empty:
        out = out.merge(stats_df, on="nome", how="left")
    return out


def filter_players(df: pd.DataFrame, search: str, roles: list[str], teams: list[str]) -> pd.DataFrame:
    out = df.copy()
    if search:
        out = out[out["nome"].astype(str).str.contains(search, case=False, na=False)]
    if roles and "ruolo" in out.columns:
        out = out[out["ruolo"].isin(roles)]
    if teams and "squadra" in out.columns:
        out = out[out["squadra"].isin(teams)]
    return out


def metric_columns(df: pd.DataFrame) -> list[str]:
    candidates = [
        "voto",
        "fantavoto",
        "voto_graph",
        "fantavoto_graph",
        "bonus_graph",
        "malus_graph",
        "quotazione_classic",
        "quotazione_mantra",
        "assists",
        "scoredGoals",
        "yellowCards",
        "redCards",
        "ownGoals",
        "win",
    ]
    return [c for c in candidates if c in df.columns]


def combine_series(stats: dict[str, pd.DataFrame], players: list[str], metric: str) -> pd.DataFrame:
    frames = []
    for player in players:
        df = stats.get(player)
        if df is None or metric not in df.columns or "giornata" not in df.columns:
            continue
        tmp = df[["giornata", metric]].copy()
        tmp[metric] = pd.to_numeric(tmp[metric], errors="coerce")
        tmp["player"] = player
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def line_chart(data: pd.DataFrame, x: str, y: str, colour: str | None = None) -> None:
    if data.empty:
        st.info("No data available for this plot.")
        return
    if px is not None:
        fig = px.line(data, x=x, y=y, color=colour, markers=True)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        if colour:
            pivot = data.pivot(index=x, columns=colour, values=y)
            st.line_chart(pivot)
        else:
            st.line_chart(data.set_index(x)[y])




def render_grid(
    df: pd.DataFrame,
    *,
    key: str,
    height: int = 420,
    selection_mode: str = "single",
    fit_columns: bool = False,
    pinned: list[str] | None = None,
):
    """Fancy table when streamlit-aggrid is installed, safe fallback otherwise."""
    if df is None or df.empty:
        st.info("No rows to display.")
        return None

    if AgGrid is None or GridOptionsBuilder is None:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)
        return None

    show_df = df.copy()
    gb = GridOptionsBuilder.from_dataframe(show_df)
    gb.configure_default_column(
        filter=True,
        sortable=True,
        resizable=True,
        editable=False,
        groupable=True,
    )
    gb.configure_selection(selection_mode=selection_mode, use_checkbox=selection_mode != "single")
    gb.configure_grid_options(
        enableRangeSelection=True,
        rowHeight=32,
        headerHeight=38,
        suppressAggFuncInHeader=True,
    )

    for col in pinned or []:
        if col in show_df.columns:
            gb.configure_column(col, pinned="left")

    numeric_cols = [c for c in show_df.columns if pd.api.types.is_numeric_dtype(show_df[c])]
    for col in numeric_cols:
        gb.configure_column(col, type=["numericColumn"], precision=2)

    if "available" in show_df.columns and JsCode is not None:
        row_style = JsCode(
            """
            function(params) {
                if (params.data.available === true) {
                    return {'backgroundColor': '#ecfdf3'};
                }
                if (params.data.available === false) {
                    return {'backgroundColor': '#fff1f2'};
                }
                return {};
            }
            """
        )
        gb.configure_grid_options(getRowStyle=row_style)

    grid_options = gb.build()
    return AgGrid(
        show_df,
        gridOptions=grid_options,
        height=height,
        width="100%",
        fit_columns_on_grid_load=fit_columns,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED if GridUpdateMode else None,
        theme="alpine",
        key=key,
    )


def render_metric_cards(metrics: list[tuple[str, object]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)


def render_auction_summary(service: AuctionService) -> None:
    players = service.players_table()
    teams = service.teams_table()
    events = service.events_table()

    sold = int((~players["available"]).sum()) if "available" in players else 0
    available = int(players["available"].sum()) if "available" in players else 0
    spent = int(teams["spent"].sum()) if "spent" in teams else 0
    remaining = int(teams["remaining_budget"].sum()) if "remaining_budget" in teams else 0

    render_metric_cards([
        ("Players sold", sold),
        ("Players available", available),
        ("Credits spent", spent),
        ("Credits remaining", remaining),
    ])

    st.markdown("#### Teams summary")
    summary_cols = ["team", "initial_budget", "spent", "remaining_budget", "players", "P", "D", "C", "A"]
    summary = teams[[c for c in summary_cols if c in teams.columns]].sort_values("remaining_budget", ascending=False)
    render_grid(summary, key="auction_summary_teams", height=260, selection_mode="single", pinned=["team"])

    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### Roster composition")
        comp_cols = ["team", "P", "D", "C", "A", "players"]
        comp = teams[[c for c in comp_cols if c in teams.columns]].copy()
        render_grid(comp, key="auction_summary_composition", height=260, selection_mode="single", pinned=["team"])

    with right:
        st.markdown("#### Recent purchases")
        recent = events[events["action"].isin(["assign", "edit_price", "release", "undo"])] if not events.empty and "action" in events else pd.DataFrame()
        if not recent.empty:
            cols = [c for c in ["timestamp", "action", "player", "team", "price", "previous_team", "previous_price"] if c in recent.columns]
            render_grid(recent[cols].tail(12).iloc[::-1], key="auction_summary_recent", height=260, selection_mode="single")
        else:
            st.info("No purchases yet.")

    st.markdown("#### Top available players")
    available_players = players[players["available"]].copy() if "available" in players else players.copy()
    c1, c2, c3 = st.columns([1, 1, 2])
    role = c1.selectbox("Role", ["All"] + sorted(available_players["ruolo"].dropna().unique().tolist()), key="summary_top_role") if "ruolo" in available_players else "All"
    sort_by = c2.selectbox("Sort by", [c for c in ["FVM", "QA", "QI"] if c in available_players.columns], key="summary_top_sort")
    n_top = c3.slider("Rows", min_value=5, max_value=50, value=20, step=5, key="summary_top_n")
    if role != "All":
        available_players = available_players[available_players["ruolo"] == role]
    if sort_by:
        available_players[sort_by] = pd.to_numeric(available_players[sort_by], errors="coerce")
        available_players = available_players.sort_values(sort_by, ascending=False)
    cols = [c for c in ["nome", "ruolo", "squadra", "QA", "FVM", "QI", "owner", "price"] if c in available_players.columns]
    render_grid(available_players[cols].head(n_top), key="auction_summary_top_available", height=390, selection_mode="single", pinned=["nome"])

    if px is not None and not teams.empty:
        st.markdown("#### Budget chart")
        budget_long = teams[["team", "spent", "remaining_budget"]].melt(id_vars="team", var_name="bucket", value_name="credits")
        fig = px.bar(budget_long, x="team", y="credits", color="bucket", barmode="stack")
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

def get_auction_service(
    *,
    year: int,
    auction_name: str,
    auction_dir: Path,
    quotazioni: pd.DataFrame,
    team_names: list[str],
    budget: int,
) -> AuctionService | None:
    store = AuctionStore(auction_dir)
    key = f"auction_service_{year}_{auction_name}_{auction_dir}"

    if key not in st.session_state:
        if store.exists(year, auction_name):
            st.session_state[key] = AuctionService(
                state=store.load(year, auction_name),
                store=store,
                auction_name=auction_name,
            )
        else:
            return None

    return st.session_state[key]


def reset_auction_service(year: int, auction_name: str, auction_dir: Path) -> None:
    key = f"auction_service_{year}_{auction_name}_{auction_dir}"
    st.session_state.pop(key, None)


# -----------------------------
# UI tabs
# -----------------------------

def render_dashboard_tabs(quotazioni: pd.DataFrame, stats: dict[str, pd.DataFrame]) -> None:
    players_df = build_players_table(quotazioni, stats)

    with st.sidebar:
        st.divider()
        st.header("Player filters")
        search = st.text_input("Search player", value="")
        roles = st.multiselect(
            "Roles",
            sorted(players_df["ruolo"].dropna().unique().tolist()) if "ruolo" in players_df else [],
        )
        teams = st.multiselect(
            "Teams",
            sorted(players_df["squadra"].dropna().unique().tolist()) if "squadra" in players_df else [],
        )

    filtered_df = filter_players(players_df, search, roles, teams)

    tab_players, tab_detail, tab_compare, tab_raw = st.tabs(["Players", "Player detail", "Compare", "Raw data"])

    with tab_players:
        visible_cols = [
            c for c in [
                "nome", "ruolo", "squadra", "QI", "QA", "FVM", "partite", "voto_mean",
                "fantavoto_mean", "goal", "assist", "yellow", "red", "url",
            ] if c in filtered_df.columns
        ]
        render_grid(filtered_df[visible_cols], key="players_grid", height=520, selection_mode="single", pinned=["nome"])

    names = filtered_df["nome"].dropna().astype(str).tolist() if "nome" in filtered_df else []
    if not names:
        return

    with tab_detail:
        selected = st.selectbox("Player", names, key="detail_player")
        player_df = stats.get(selected)
        if player_df is None:
            st.warning("No stats found for selected player.")
        else:
            attrs = player_df.attrs
            cols = st.columns(5)
            cols[0].metric("Team", attrs.get("team") or "-")
            cols[1].metric("Rows", len(player_df))
            cols[2].metric("Mean voto", f"{pd.to_numeric(player_df.get('voto'), errors='coerce').mean():.2f}" if "voto" in player_df else "-")
            cols[3].metric("Mean fantavoto", f"{pd.to_numeric(player_df.get('fantavoto'), errors='coerce').mean():.2f}" if "fantavoto" in player_df else "-")
            qa_value = filtered_df.loc[filtered_df["nome"] == selected, "QA"].iloc[0] if "QA" in filtered_df else "-"
            cols[4].metric("Current QA", qa_value)

            available_metrics = metric_columns(player_df)
            metric = st.selectbox(
                "Metric",
                available_metrics,
                index=available_metrics.index("quotazione_classic") if "quotazione_classic" in available_metrics else 0,
            )
            plot_df = player_df[["giornata", metric]].copy() if "giornata" in player_df and metric in player_df else pd.DataFrame()
            if not plot_df.empty:
                plot_df[metric] = pd.to_numeric(plot_df[metric], errors="coerce")
            line_chart(plot_df, "giornata", metric)

            st.markdown("#### Matchweek data")
            render_grid(player_df, key="player_matchweek_grid", height=440, selection_mode="single")

            with st.expander("Player attributes"):
                st.json(attrs)

    with tab_compare:
        selected_players = st.multiselect("Players to compare", names, default=names[: min(3, len(names))])
        all_metrics = sorted({m for p in selected_players if p in stats for m in metric_columns(stats[p])})
        metric = st.selectbox(
            "Comparison metric",
            all_metrics,
            index=all_metrics.index("quotazione_classic") if "quotazione_classic" in all_metrics else 0,
        ) if all_metrics else None

        if selected_players and metric:
            comp = combine_series(stats, selected_players, metric)
            line_chart(comp, "giornata", metric, "player")

            rows = []
            for player in selected_players:
                df = stats.get(player)
                if df is None or metric not in df.columns or "giornata" not in df.columns:
                    continue
                tmp = df[["giornata", metric]].copy()
                tmp[metric] = pd.to_numeric(tmp[metric], errors="coerce")
                rows.append({
                    "player": player,
                    "mean": tmp[metric].mean(),
                    "min": tmp[metric].min(),
                    "max": tmp[metric].max(),
                    "last": tmp.sort_values("giornata")[metric].dropna().iloc[-1] if tmp[metric].notna().any() else None,
                })
            render_grid(pd.DataFrame(rows), key="compare_summary_grid", height=260, selection_mode="single", pinned=["player"])

    with tab_raw:
        st.markdown("#### Quotazioni")
        render_grid(quotazioni, key="raw_quotazioni_grid", height=520, selection_mode="single", pinned=["nome"])
        st.markdown("#### Stats keys")
        st.write(sorted(stats.keys()))


def render_auction_tab(year: int, quotazioni: pd.DataFrame) -> None:
    st.header("Auction manager")

    with st.sidebar:
        st.divider()
        st.header("Auction setup")
        auction_name = st.text_input("Auction name", value="default")
        auction_dir = Path(st.text_input("Auction directory", value=str(DEFAULT_AUCTIONS_DIR)))
        budget = st.number_input("Initial budget", min_value=1, value=500, step=1)
        teams_raw = st.text_area("Team names, one per line", value="Giorgio\nLuca\nMarco\nAndrea")
        team_names = [line.strip() for line in teams_raw.splitlines() if line.strip()]

        col_create, col_reload = st.columns(2)
        create_clicked = col_create.button("Create / overwrite")
        reload_clicked = col_reload.button("Reload")

    store = AuctionStore(auction_dir)

    if create_clicked:
        try:
            service = AuctionService.create(
                year=year,
                team_names=team_names,
                budget=int(budget),
                players_df=quotazioni,
                store=store,
                auction_name=auction_name,
            )
            reset_auction_service(year, auction_name, auction_dir)
            st.session_state[f"auction_service_{year}_{auction_name}_{auction_dir}"] = service
            st.success("Auction created.")
        except AuctionError as exc:
            st.error(str(exc))

    if reload_clicked:
        reset_auction_service(year, auction_name, auction_dir)
        st.success("Auction reloaded from disk.")

    service = get_auction_service(
        year=year,
        auction_name=auction_name,
        auction_dir=auction_dir,
        quotazioni=quotazioni,
        team_names=team_names,
        budget=int(budget),
    )

    if service is None:
        st.info("Create an auction from the sidebar or reload an existing one.")
        existing = store.list_auctions()
        if existing:
            st.markdown("Existing auctions:")
            st.write([str(p) for p in existing])
        return

    tab_summary, tab_board, tab_teams, tab_players, tab_events = st.tabs(["Summary", "Auction board", "Teams", "Players", "Events"])

    with tab_summary:
        render_auction_summary(service)

    with tab_board:
        players_table = service.players_table()
        available = players_table[players_table["available"]].copy()

        left, right = st.columns([2, 1])
        with left:
            search = st.text_input("Search available player", value="", key="auction_search")
            if search:
                available = available[available["nome"].astype(str).str.contains(search, case=False, na=False)]
            roles = st.multiselect("Role", sorted(available["ruolo"].dropna().unique().tolist()), key="auction_roles")
            if roles:
                available = available[available["ruolo"].isin(roles)]
            render_grid(available[[c for c in ["nome", "ruolo", "squadra", "QA", "FVM", "QI"] if c in available.columns]], key="auction_available_grid", height=520, selection_mode="single", pinned=["nome"])

        with right:
            player_options = available["nome"].astype(str).tolist()
            buyer_options = sorted(service.state.teams.keys())
            selected_player = st.selectbox("Player", player_options, key="assign_player") if player_options else None
            selected_team = st.selectbox("Buyer", buyer_options, key="assign_team") if buyer_options else None
            price = st.number_input("Price", min_value=1, value=1, step=1, key="assign_price")

            if selected_player:
                row = players_table[players_table["nome"] == selected_player].iloc[0]
                st.caption(f"{row.get('ruolo')} | {row.get('squadra')} | QA {row.get('QA')} | FVM {row.get('FVM')}")

            if st.button("Assign player", type="primary"):
                try:
                    service.assign_player(str(selected_player), str(selected_team), int(price))
                    st.success(f"Assigned {selected_player} to {selected_team} for {price}.")
                    st.rerun()
                except AuctionError as exc:
                    st.error(str(exc))

            if st.button("Undo last action"):
                try:
                    service.undo_last()
                    st.success("Last action undone.")
                    st.rerun()
                except AuctionError as exc:
                    st.error(str(exc))

        st.markdown("#### Budgets")
        render_grid(service.teams_table(), key="auction_board_teams_grid", height=260, selection_mode="single", pinned=["team"])

        st.markdown("#### Recent events")
        events = service.events_table()
        render_grid(events.tail(10).iloc[::-1], key="auction_board_events_grid", height=260, selection_mode="single")

    with tab_teams:
        teams_df = service.teams_table()
        render_grid(teams_df, key="auction_teams_grid", height=320, selection_mode="single", pinned=["team"])

        selected_team = st.selectbox("Team roster", sorted(service.state.teams.keys()), key="roster_team")
        render_grid(service.roster_table(selected_team), key="auction_roster_grid", height=420, selection_mode="single", pinned=["nome"])

    with tab_players:
        players_table = service.players_table()
        owner_filter = st.multiselect(
            "Owner",
            sorted([x for x in players_table["owner"].dropna().unique().tolist()]),
            key="owner_filter",
        )
        only_available = st.checkbox("Available only", value=False)
        table = players_table.copy()
        if owner_filter:
            table = table[table["owner"].isin(owner_filter)]
        if only_available:
            table = table[table["available"]]
        render_grid(table, key="auction_players_grid", height=520, selection_mode="single", pinned=["nome"])

        st.markdown("#### Edit / release")
        assigned = players_table[~players_table["available"]]
        if assigned.empty:
            st.info("No assigned players yet.")
        else:
            selected = st.selectbox("Assigned player", assigned["nome"].astype(str).tolist(), key="edit_player")
            current = assigned[assigned["nome"] == selected].iloc[0]
            new_price = st.number_input("New price", min_value=1, value=int(current["price"]), step=1, key="edit_price")

            c1, c2 = st.columns(2)
            if c1.button("Edit price"):
                try:
                    service.edit_price(selected, int(new_price))
                    st.success("Price updated.")
                    st.rerun()
                except AuctionError as exc:
                    st.error(str(exc))
            if c2.button("Release player"):
                try:
                    service.release_player(selected)
                    st.success("Player released.")
                    st.rerun()
                except AuctionError as exc:
                    st.error(str(exc))

    with tab_events:
        render_grid(service.events_table(), key="auction_events_grid", height=560, selection_mode="single")
        path = store.path_for(year, auction_name)
        st.caption(f"State file: {path}")


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    st.set_page_config(page_title="Fantacalcio Dashboard", layout="wide")
    st.title("Fantacalcio Dashboard")

    with st.sidebar:
        st.header("Input")
        year = int(st.number_input("Reference year", min_value=2000, max_value=2100, value=2026, step=1))
        cache_dir = Path(st.text_input("Cache directory", value=str(DEFAULT_CACHE_DIR)))

        st.divider()
        st.header("Refresh cache")
        proxy = st.text_input("Proxy", value="")
        max_workers = st.slider("Workers", min_value=1, max_value=40, value=10)
        verify = st.checkbox("TLS verify", value=True)
        if st.button("Force scrape and refresh cache"):
            with st.spinner("Scraping..."):
                refresh_cache(year, cache_dir, proxy or None, max_workers, verify)
            st.success("Cache refreshed.")

    try:
        quotazioni = load_quotazioni(str(cache_dir), year)
        stats = load_stats(str(cache_dir), year)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    main_tab, auction_tab = st.tabs(["Dashboard", "Auction"])
    with main_tab:
        render_dashboard_tabs(quotazioni, stats)
    with auction_tab:
        render_auction_tab(year, quotazioni)


if __name__ == "__main__":
    main()
