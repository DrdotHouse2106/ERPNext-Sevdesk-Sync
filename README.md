# ERPNext-Sevdesk-Sync

Kleine, spezifische ERPNext-App: synct die **Bruttopreise** der Standard-Preisliste
aus ERPNext als **Nettopreise** nach sevDesk.

Das Projekt ist als echte ERPNext-/Frappe-App (`sevdesk_sync`) aufgebaut, die auf
einer ERPNext-Instanz installiert wird und dort läuft — kein externes Skript, keine
separaten API-Zugangsdaten für ERPNext nötig.

## Funktionsweise

1. Die Bruttopreise (`price_list_rate`) werden für alle Artikel der konfigurierten
   ERPNext-Preisliste **direkt über die Frappe-ORM** (`frappe.get_all`) gelesen,
   da die App innerhalb von ERPNext läuft.
2. Für jeden ERPNext-Artikel (`item_code`) wird per `partNumber` der passende
   Artikel (Part) in sevDesk über die sevDesk-REST-API gesucht.
3. Der Bruttopreis wird mit dem in sevDesk bereits hinterlegten Steuersatz
   (`taxRate`) des Artikels in einen Nettopreis umgerechnet:
   `netto = brutto / (1 + steuersatz / 100)`.
   Ist am sevDesk-Artikel noch kein Steuersatz gesetzt, wird ersatzweise der
   in den App-Einstellungen hinterlegte `Default Tax Rate` verwendet; ist beides
   nicht vorhanden, wird der Artikel übersprungen (mit einer Warnung im Log).
4. Weicht der berechnete Nettopreis vom aktuell in sevDesk hinterlegten Preis ab,
   wird der sevDesk-Artikel per API aktualisiert (`price` = netto, `priceGross`
   = brutto).
5. Der Sync läuft automatisch **einmal täglich** über Frappes Scheduler
   (`scheduler_events` in `hooks.py`).

Artikel, die in ERPNext eine Preisliste-Zeile haben, aber in sevDesk keinen Artikel
mit passender `partNumber`, werden übersprungen und gesammelt als Warnung geloggt.

## Installation in ERPNext (bench)

```bash
bench get-app sevdesk_sync /pfad/zu/ERPNext-Sevdesk-Sync/sevdesk_sync
bench --site <site-name> install-app sevdesk_sync
bench --site <site-name> migrate
```

## Konfiguration

Nach der Installation in ERPNext unter **SevDesk Sync Settings** (Single-DocType)
öffnen und ausfüllen:

| Feld                     | Beschreibung                                                                 |
|---------------------------|-------------------------------------------------------------------------------|
| ERPNext Price List        | Name der zu exportierenden Preisliste (Default: `Standard Selling`)           |
| Default Tax Rate (%)      | Fallback-Steuersatz, falls ein sevDesk-Artikel noch keinen hat               |
| sevDesk API Base URL      | sevDesk-API-Basis-URL (Default: `https://my.sevdesk.de/api/v1`)               |
| sevDesk API Token         | API-Token aus sevDesk (Einstellungen → Benutzer → API), wird verschlüsselt gespeichert |
| Dry Run                   | Wenn aktiviert, wird nur simuliert/geloggt, nichts in sevDesk geschrieben     |
| Last Sync On / Summary    | Read-only, wird nach jedem Lauf automatisch aktualisiert                     |

## Nutzung

Der Sync läuft automatisch täglich über den Frappe-Scheduler. Ein manueller Lauf
ist über die Bench-Console möglich:

```bash
bench --site <site-name> execute sevdesk_sync.tasks.run_sync
```

Oder, mit Berechtigungsprüfung, als whitelisted Methode (z. B. über die
Frappe-API oder `bench --site <site-name> execute sevdesk_sync.tasks.run_sync_now`).

## Tests

Die Kernlogik (`price_sync.py`, `sevdesk_client.py`, `erpnext_source.py`) ist reines
Python und lässt sich ohne laufende Bench-/ERPNext-Instanz testen. Für
`erpnext_source.py` wird `frappe` dabei durch ein minimales Fake-Modul ersetzt.

```bash
PYTHONPATH=sevdesk_sync python3 -m unittest discover -s tests -v
```

`sevdesk_sync_settings.py` (die DocType-Controller-Klasse) benötigt hingegen eine
echte Bench-/Site-Umgebung und wird nicht durch diese Tests abgedeckt.
