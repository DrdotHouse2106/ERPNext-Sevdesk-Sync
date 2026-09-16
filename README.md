# ERPNext-Sevdesk-Sync

Kleiner spezifischer ERPNext zu SevDesk Sync.

Dieses Tool exportiert die **Bruttopreise** einer ERPNext-Preisliste (standardmäßig
`Standard Selling`) nach sevDesk und schreibt sie dort als **Nettopreise** in die
passenden Artikel (Parts).

## Funktionsweise

1. Die Bruttopreise (`price_list_rate`) werden für alle Artikel der konfigurierten
   ERPNext-Preisliste über die Frappe-REST-API abgefragt.
2. Für jeden ERPNext-Artikel (`item_code`) wird per `partNumber` der passende Artikel
   in sevDesk gesucht.
3. Der Bruttopreis wird mit dem in sevDesk bereits hinterlegten Steuersatz
   (`taxRate`) des Artikels in einen Nettopreis umgerechnet:
   `netto = brutto / (1 + steuersatz / 100)`.
   Ist am sevDesk-Artikel noch kein Steuersatz gesetzt, wird ersatzweise
   `DEFAULT_TAX_RATE` verwendet; ist beides nicht vorhanden, wird der Artikel
   übersprungen (mit einer Warnung im Log).
4. Weicht der berechnete Nettopreis vom aktuell in sevDesk hinterlegten Preis ab,
   wird der sevDesk-Artikel per API aktualisiert (`price` = netto, `priceGross`
   = brutto).

Artikel, die in ERPNext eine Preisliste-Zeile haben, aber in sevDesk keinen Artikel
mit passender `partNumber`, werden übersprungen und am Ende gesammelt als Warnung
geloggt.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Die einzige Laufzeitabhängigkeit ist [`requests`](https://pypi.org/project/requests/).

## Konfiguration

```bash
cp .env.example .env
```

Anschließend `.env` mit den eigenen Zugangsdaten befüllen:

| Variable              | Beschreibung                                                                 |
|------------------------|-------------------------------------------------------------------------------|
| `ERPNEXT_URL`          | Basis-URL der ERPNext-/Frappe-Site, z. B. `https://firma.erpnext.com`         |
| `ERPNEXT_API_KEY`      | API-Key eines ERPNext-Benutzers mit Leserechten auf `Item Price`               |
| `ERPNEXT_API_SECRET`   | Zugehöriges API-Secret                                                        |
| `ERPNEXT_PRICE_LIST`   | Name der zu exportierenden Preisliste (Default: `Standard Selling`)           |
| `SEVDESK_API_TOKEN`    | API-Token aus sevDesk (Einstellungen → Benutzer → API)                        |
| `SEVDESK_BASE_URL`     | sevDesk-API-Basis-URL (Default: `https://my.sevdesk.de/api/v1`)               |
| `DEFAULT_TAX_RATE`     | Fallback-Steuersatz in Prozent, falls ein sevDesk-Artikel noch keinen hat     |
| `DRY_RUN`              | `true`/`false` – bei `true` wird nichts geschrieben, nur geloggt              |

## Nutzung

```bash
erpnext-sevdesk-sync
```

Optionen:

```bash
erpnext-sevdesk-sync --dry-run       # nur simulieren, nichts in sevDesk ändern
erpnext-sevdesk-sync --env-file prod.env
erpnext-sevdesk-sync -v              # ausführlichere Logs
```

Alternativ ohne Installation direkt als Modul:

```bash
python3 -m erpnext_sevdesk_sync.cli --dry-run
```

## Tests

Die Tests nutzen ausschließlich die Python-Standardbibliothek (`unittest`), es wird
keine zusätzliche Abhängigkeit benötigt:

```bash
python3 -m unittest discover -s tests -v
```
