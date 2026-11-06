# Installeren op de Raspberry Pi

De app draait altijd op de Pi 3B+. De AI-coach draait op de laptop, want de Pi
heeft met 1 GB RAM te weinig geheugen voor een taalmodel. Staat de laptop uit,
dan werkt alles behalve de coach.

## 1. De Pi voorbereiden

Installeer **Raspberry Pi OS Lite (64-bit)** met Raspberry Pi Imager. Het project
vereist Python 3.14, en `uv` installeert die zelf op een 64-bit systeem.

De bestanden in `deploy/` gaan uit van de gebruiker `pi` en de map
`/home/pi/trainmetrics`. Gebruik je iets anders, pas die bestanden dan aan.

```bash
sudo timedatectl set-timezone Europe/Brussels
curl -LsSf https://astral.sh/uv/install.sh | sh
```

De tijdzone is nodig omdat geïmporteerde trainingen in lokale tijd worden
opgeslagen.

## 2. De app installeren

```bash
cd ~
git clone <url-van-je-repo> trainmetrics
cd trainmetrics/backend
uv sync --no-dev
uv run alembic upgrade head
```

Wil je je bestaande database meenemen? Stuur ze dan vanaf de laptop door, in
plaats van `alembic upgrade head` op een lege database te gebruiken:

```bash
scp database/trainmetrics.db pi@<ip-van-de-pi>:trainmetrics/database/
```

Die database is al gemigreerd, dus ze werkt meteen.

## 3. Automatisch starten en dagelijkse back-up

```bash
cd ~/trainmetrics
sudo cp deploy/trainmetrics* /etc/systemd/system/
sudo nano /etc/systemd/system/trainmetrics.service   # zet OLLAMA_URL op het IP van de laptop
sudo systemctl daemon-reload
sudo systemctl enable --now trainmetrics trainmetrics-backup.timer
```

De app staat nu op `http://<ip-van-de-pi>:8000`. Geef de Pi in je router een vast
IP-adres, zodat dat adres niet verandert.

## 4. Back-ups echt veilig maken

De timer maakt elke nacht een kopie in `data/backups/` en bewaart de laatste 30.
Die kopieën staan op dezelfde SD-kaart als de database, en SD-kaarten gaan
geregeld stuk. Haal ze daarom ook naar de laptop:

```bash
rsync -a pi@<ip-van-de-pi>:trainmetrics/data/backups/ ~/trainmetrics-backups/
```

Terugzetten: stop de app, kopieer een back-up over `database/trainmetrics.db` en
start de app opnieuw. Probeer dit minstens één keer, zodat je weet dat het werkt.

```bash
sudo systemctl stop trainmetrics
cp data/backups/trainmetrics-<datum>.db database/trainmetrics.db
sudo systemctl start trainmetrics
```

## 5. De coach op de laptop

Installeer [Ollama](https://ollama.com/download) en haal een model op:

```bash
ollama pull qwen3:4b
```

Laat Ollama luisteren op je netwerk, zodat de Pi erbij kan:

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

```bash
sudo systemctl restart ollama
```

Ollama heeft geen login, dus iedereen op je netwerk kan het dan gebruiken. Doe
dit alleen op je eigen thuisnetwerk. Op een Linux-laptop met UFW kun je de poort
beperken tot de Pi:

```bash
sudo ufw allow from <ip-van-de-pi> to any port 11434 proto tcp
```

Test vanaf de Pi:

```bash
curl http://<ip-van-de-laptop>:11434/api/tags
```

Kies het model dat bij de laptop past en zet de naam in `OLLAMA_MODEL`. Hoe groter
het model, hoe beter de antwoorden, maar ook hoe trager en hoe meer geheugen het
vraagt. Een antwoord dat te lang duurt, stopt na `OLLAMA_TIMEOUT` seconden
(standaard 180).

## 6. Veiligheid

De app heeft geen login. Iedereen op je netwerk kan je gegevens zien en wijzigen.

- Stel poort 8000 **nooit** open via port forwarding op je router.
- Wil je er onderweg bij, gebruik dan een VPN zoals
  [Tailscale](https://tailscale.com/), met een gratis abonnement voor persoonlijk gebruik.

## Updaten

```bash
cd ~/trainmetrics
git pull
cd backend
uv sync --no-dev
uv run alembic upgrade head
sudo systemctl restart trainmetrics
```
