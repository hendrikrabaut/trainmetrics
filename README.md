# TrainMetrics

Persoonlijk trainingsplatform dat lokaal draait: krachttraining, duursport,
lichaamsmetingen en materiaal, met import van sporthorloges, analyses en een
lokale AI-coach.

- **Backend:** FastAPI, SQLAlchemy, SQLite, Alembic (`backend/`)
- **Frontend:** HTML, CSS en JavaScript zonder buildstap (`frontend/`)
- **Coach:** Ollama, op een andere computer in je netwerk

## Lokaal starten

Vereist [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

De app staat op <http://localhost:8000> en de API-documentatie op `/docs`.

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
- Schemawijzigingen gaan via Alembic. `database/schema.sql` is alleen referentie.

## Meer

- [Installeren op de Raspberry Pi en de coach instellen](docs/deployment.md)
