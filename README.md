# ERPNext-Sevdesk-Sync

Kleine, spezifische ERPNext-App: überträgt den Preis der Standard-Preisliste aus
ERPNext (dort als Bruttopreis geführt) unverändert als **Nettopreis** nach sevDesk.
Das heißt konkret: ERPNext 100 € (Brutto-Feld) → sevDesk 100 € **netto**, sevDesk
zeigt/berechnet daraus dann 119 € brutto (bei 19 % USt.). Es wird also **keine**
Steuer aus dem ERPNext-Preis herausgerechnet, sondern der Zahlenwert direkt als
sevDesk-Nettopreis übernommen.

Das Projekt ist als echte ERPNext-/Frappe-App (`sevdesk_sync`) aufgebaut, die auf
einer ERPNext-Instanz installiert wird und dort läuft — kein externes Skript, keine
separaten API-Zugangsdaten für ERPNext nötig.

## Funktionsweise

1. Die Preise (`price_list_rate`) werden für alle Artikel der konfigurierten
   ERPNext-Preisliste **direkt über die Frappe-ORM** (`frappe.get_all`) gelesen,
   zusammen mit dem Artikelnamen (für ggf. neu anzulegende sevDesk-Artikel).
2. Für jeden ERPNext-Artikel (`item_code`) wird per `partNumber` der passende
   Artikel (Part) in sevDesk über die sevDesk-REST-API gesucht.
3. **Existiert der Artikel in sevDesk bereits:** Der ERPNext-Preis wird 1:1 als
   sevDesk-Nettopreis (`price`) übernommen. Der sevDesk-Bruttopreis (`priceGross`)
   wird daraus mit dem am sevDesk-Artikel hinterlegten Steuersatz (`taxRate`)
   berechnet: `brutto = netto * (1 + steuersatz / 100)`. Hat der sevDesk-Artikel
   noch keinen Steuersatz, wird ersatzweise der in den App-Einstellungen
   hinterlegte `Default Tax Rate` verwendet. Ist beides nicht vorhanden, wird der
   Artikel übersprungen (mit einer Warnung im Log). Weicht der neue Nettopreis
   vom aktuellen ab, wird der sevDesk-Artikel per API aktualisiert.
4. **Existiert der Artikel in sevDesk noch nicht:** Er wird neu angelegt
   (`partNumber` = ERPNext `item_code`, Name = ERPNext-Artikelbezeichnung), mit
   dem ERPNext-Preis als Nettopreis und dem daraus berechneten Bruttopreis.
   Dafür müssen `Default Tax Rate` **und** `sevDesk Default Unity ID` (die
   sevDesk-Einheit, z. B. "Stück") in den Einstellungen gesetzt sein — fehlt
   eines von beiden, wird der Artikel übersprungen (mit Warnung im Log).
5. Der Sync läuft automatisch **einmal täglich** über Frappes Scheduler
   (`scheduler_events` in `hooks.py`).

## Installation in ERPNext (bench)

Direkt von GitHub:

```bash
bench get-app https://github.com/DrdotHouse2106/ERPNext-Sevdesk-Sync
bench --site <site-name> install-app sevdesk_sync
bench --site <site-name> migrate
```

Oder von einem bereits lokal geklonten Repo:

```bash
bench get-app sevdesk_sync /pfad/zu/ERPNext-Sevdesk-Sync
bench --site <site-name> install-app sevdesk_sync
bench --site <site-name> migrate
```

## Konfiguration

Nach der Installation in ERPNext unter **SevDesk Sync Settings** (Single-DocType)
öffnen und ausfüllen:

| Feld                     | Beschreibung                                                                 |
|---------------------------|-------------------------------------------------------------------------------|
| ERPNext Price List        | Name der zu exportierenden Preisliste (Default: `Standard Selling`)           |
| Default Tax Rate (%)      | Steuersatz für Artikel ohne sevDesk-Steuersatz und **Pflichtfeld** für die Neuanlage von Artikeln |
| sevDesk API Base URL      | sevDesk-API-Basis-URL (Default: `https://my.sevdesk.de/api/v1`)               |
| sevDesk API Token         | API-Token aus sevDesk (Einstellungen → Benutzer → API), wird verschlüsselt gespeichert |
| sevDesk Default Unity ID  | sevDesk-Einheit (z. B. "Stück") für neu anzulegende Artikel; **Pflichtfeld** für die Neuanlage von Artikeln, zu finden unter sevDesk → Einstellungen → Stammdaten → Einheiten oder via `GET /Unity` |
| Dry Run                   | Wenn aktiviert, wird nur simuliert/geloggt, nichts in sevDesk geschrieben oder angelegt |
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
python3 -m unittest discover -s tests -v
```

`sevdesk_sync_settings.py` (die DocType-Controller-Klasse) benötigt hingegen eine
echte Bench-/Site-Umgebung und wird nicht durch diese Tests abgedeckt.
