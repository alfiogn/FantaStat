# Prompt di aggiornamento per l’altra chat

Aggiorna **fantastat** usando `scraper.py` e `scraped_data_structure.md` allegati come sorgenti autoritative.

## Correzione stagione corrente

Ogni giocatore in `stats<year>.json` deve avere una riga per ogni ascissa positiva di `player-price-graph`, anche quando Classic e Mantra sono null. Le ascisse sono salvate in `df.attrs["price_graph_matchweeks"]` e il massimo in `price_graph_max_matchweek`.

Per ogni giornata assente dalla tabella giocatore, usa il calendario soltanto per trovare la partita della squadra e aggiungi prima del dump una riga con `record_type="calendar_placeholder"`, `played=False`, `is_placeholder=True`, `status="scheduled"`. Copia i dati della partita, lascia null performance e quotazioni, usa eventi vuoti e contatori a zero.

## Risoluzione squadra

Non usare prioritariamente `quotazioni.squadra`: può essere abbreviata, per esempio `Int`, mentre il calendario usa `Inter`. Risolvi la squadra in questo ordine:

1. `player_df.attrs["team"]`;
2. `player_df.attrs["bridge"]["teamName"]`;
3. `quotazioni.squadra`;
4. slug finale di `player_df.attrs["team_url"]`.

Confronta i candidati con i nomi completi presenti in `calendar_df.team_home` e `calendar_df.team_away`. Come fallback accetta un prefisso soltanto se identifica una sola squadra. Salva `calendar_team_resolved` e `quotation_team` negli attrs per diagnosi.

Il calendario non deve imporre le giornate attese. Invalida le vecchie cache tramite `SCRAPER_SCHEMA_VERSION = 4`. Prima della serializzazione verifica che tutte le giornate attese siano presenti. In caso contrario mostra anche squadra risolta, squadra quotazioni e squadra pagina giocatore.

Per statistiche e medie filtra solo `record_type == "player_page"` oppure `played == True`. Il progetto si chiama **fantastat**.
