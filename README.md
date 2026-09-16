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
   eines von beiden, wird der Artikel übersprungen (mit Warnung im Log). Ist
   der ERPNext-Artikel deaktiviert, wird stattdessen **kein** neuer sevDesk-Artikel
   angelegt.
5. **Wird ein ERPNext-Artikel deaktiviert** (Feld „Disabled"), wird der passende
   sevDesk-Artikel beim nächsten Sync auf inaktiv gesetzt (`status = 50`), ohne
   ihn zu löschen. Wird er in ERPNext wieder aktiviert, wird der sevDesk-Artikel
   entsprechend wieder auf aktiv gesetzt (`status = 100`).
6. Der Sync läuft automatisch **einmal täglich** über Frappes Scheduler
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

| Feld                                | Beschreibung                                                                 |
|--------------------------------------|-------------------------------------------------------------------------------|
| Synchronisierung aktiv               | Ein/Aus-Schalter für den täglichen automatischen Sync (Default: an). Deaktiviert nur den Scheduler-Lauf, die Buttons unten funktionieren immer |
| ERPNext-Preisliste                   | Name der zu exportierenden Preisliste (Default: `Standard Selling`)           |
| Ausgeschlossene Artikelgruppen        | Mehrfachauswahl von ERPNext-Artikelgruppen, deren Artikel komplett vom Sync ausgenommen werden (weder aktualisiert noch in sevDesk neu angelegt). Wirkt nicht automatisch auf Unterartikelgruppen |
| Nur syncen, wenn Feld befüllt ist (Feldname) | Technischer Feldname eines Artikel-Felds (z. B. eines Custom Fields). Ist das gesetzt, werden nur Artikel synct, bei denen dieses Feld einen Wert hat; leer lassen, um alle Artikel der Preisliste zu syncen. Feldname finden unter Einstellungen → Customize Form → Item → Feld anklicken → „Field Name" |
| Standard-Steuersatz (%)              | Steuersatz für Artikel ohne sevDesk-Steuersatz und **Pflichtfeld** für die Neuanlage von Artikeln |
| sevDesk-API-Basis-URL                | sevDesk-API-Basis-URL (Default: `https://my.sevdesk.de/api/v1`)               |
| sevDesk-API-Token                    | API-Token aus sevDesk (Einstellungen → Benutzer → API), wird verschlüsselt gespeichert |
| sevDesk-Standardeinheit (ID)         | sevDesk-Einheit (z. B. "Stück") für neu anzulegende Artikel; **Pflichtfeld** für die Neuanlage von Artikeln, zu finden unter sevDesk → Einstellungen → Stammdaten → Einheiten oder via `GET /Unity` |
| Trockenlauf                          | Wenn aktiviert, wird bei jedem Sync (auch dem geplanten) nur simuliert/geloggt, nichts in sevDesk geschrieben oder angelegt |
| Letzte Synchronisierung am / Zusammenfassung | Read-only, wird nach jedem echten Lauf automatisch aktualisiert (nicht beim manuellen Trockenlauf-Button) |

Oben auf der Settings-Seite gibt es drei Buttons:

- **Verbindung testen** — prüft, ob sevDesk-API-Basis-URL und Token funktionieren, ohne etwas zu ändern.
- **Trockenlauf starten** — führt den Sync sofort im Trockenlauf-Modus aus (unabhängig vom Trockenlauf-Häkchen), schreibt/legt nichts in sevDesk an, und zeigt das Ergebnis direkt an.
- **Jetzt synchronisieren** — führt den echten Sync sofort aus (mit Sicherheitsabfrage, da dabei tatsächlich in sevDesk geschrieben bzw. angelegt wird).

Beide Buttons zeigen nach dem Lauf eine Zusammenfassung sowie einen Link zum
zugehörigen **SevDesk Sync Log**-Eintrag (siehe unten) mit der vollständigen Liste.

### Trockenlauf-Häkchen vs. „Trockenlauf starten"-Button

Das Häkchen wirkt auf den **täglichen automatischen** Sync (Scheduler) — damit kann
die Automatik dauerhaft im Simulationsmodus laufen (z. B. während der Testphase),
ohne dass man jeden Tag manuell eingreifen muss. Der Button „Trockenlauf starten"
ist dagegen ein einmaliger, sofortiger Test unabhängig vom Häkchen — beide sind also
für unterschiedliche Situationen gedacht und schließen sich nicht aus.

## Übersicht der Änderungen (SevDesk Sync Log)

Jeder Lauf (geplant, Trockenlauf oder manuell über „Jetzt synchronisieren") erzeugt
einen Eintrag im DocType **SevDesk Sync Log** mit Zeitpunkt, Zähler
(angelegt/aktualisiert/bereits synchron/übersprungen) und Zusammenfassung. Über den
Link „Details ansehen" bzw. direkt in ERPNext gelangt man zu den zugehörigen
**SevDesk Sync Log Item**-Zeilen — einer Zeile pro angelegtem, aktualisiertem oder
übersprungenem (mit Grund) Artikel. Das ist eine normale ERPNext-Listenansicht:
filter-, sortier- und exportierbar (z. B. nach Excel). Artikel, die bereits synchron
waren, werden dort nicht einzeln aufgeführt (nur als Zähler im Log-Kopf), um die
Tabelle bei großen Katalogen nicht unnötig aufzublähen.

## Nutzung

Der Sync läuft automatisch täglich über den Frappe-Scheduler, sofern „Synchronisierung
aktiv" angehakt ist. Ein manueller Lauf ist auch über die Bench-Console möglich:

```bash
bench --site <site-name> execute sevdesk_sync.tasks.run_sync_now
```

`run_sync_now` respektiert dabei das „Trockenlauf"-Häkchen aus den Settings; für einen
erzwungenen Trockenlauf unabhängig davon gibt es `sevdesk_sync.tasks.run_dry_run` (das,
was auch der „Trockenlauf starten"-Button aufruft) sowie `sevdesk_sync.tasks.test_connection`
für den reinen Verbindungstest.

## Tests

Die Kernlogik (`price_sync.py`, `sevdesk_client.py`, `erpnext_source.py`) ist reines
Python und lässt sich ohne laufende Bench-/ERPNext-Instanz testen. Für
`erpnext_source.py` wird `frappe` dabei durch ein minimales Fake-Modul ersetzt.

```bash
python3 -m unittest discover -s tests -v
```

`sevdesk_sync_settings.py` (die DocType-Controller-Klasse) benötigt hingegen eine
echte Bench-/Site-Umgebung und wird nicht durch diese Tests abgedeckt.
