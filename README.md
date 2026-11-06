# TrainMetrics

Persoonlijk trainingsplatform dat lokaal draait: krachttraining, duursport,
lichaamsmetingen en materiaal, met Polar-sync, schattingen in de stijl van Strava,
XP en trofeeën, en de Coach: een norse bokstrainer die je trainingsplannen
maakt. Plannen kun je zelf aanpassen en als iCal-bestand naar je agenda sturen.

- **Backend:** FastAPI, SQLAlchemy, SQLite, Alembic (`backend/`)
- **Frontend:** HTML, CSS en JavaScript zonder buildstap (`frontend/`)
- **Trainingsplannen:** vaste regels in de backend, dus ze werken altijd
- **Praten met de coach:** Ollama, op een andere computer in je netwerk
- **Polar:** de AccessLink-API, plus import van FIT-, GPX- en TCX-bestanden

## Lokaal starten

Vereist [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
cp ../.env.example .env   # vul in wat je gebruikt; leeg laten mag
uv run alembic upgrade head
uv run --env-file .env uvicorn app.main:app --reload --port 8001
```

De app staat op <http://localhost:8001> en de API-documentatie op `/docs`.

Een database die van vóór de migraties dateert, zet je eerst op de juiste versie
met `uv run alembic stamp 0001`. Daarna werkt `upgrade head` gewoon.

## Testen

```bash
cd backend
uv run pytest
```

De tests gebruiken een tijdelijke database en raken je echte data niet.

## Afspraken in de data

- Afstand in meter, duur in seconden, gewicht in kilogram.
- `average_speed` staat altijd in m/s. De frontend rekent om naar km/u of tempo.
- XP, levels, quests en badges worden telkens uit de trainingen berekend en niet
  opgeslagen. Verwijder je een training, dan verdwijnt de XP ervan ook.
- Schemawijzigingen gaan via Alembic. `database/schema.sql` is alleen referentie.

## Meer

- [Installeren op de Raspberry Pi, Polar koppelen en de coach instellen](docs/deployment.md)

De racetijden in de Polar-kolom komen uit de
Running Index-tabel in de handleidingen van Polar.
