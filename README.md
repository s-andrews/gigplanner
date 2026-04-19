# Gig Planner

Gig Planner is a small web application for running bands and managing gigs.

It is designed to help band leaders and players keep everything in one place:

- create bands
- maintain band line-ups and default part assignments
- create and edit gigs
- assign players to parts
- collect availability responses from players
- review responses across the full band
- let players see their gigs from multiple bands on one dashboard

The application is built with Flask and uses SQLite for storage by default.

## Main Features

- Band setup with player management, co-admins, parts, and default assignments
- Gig admin for creating gigs and editing line-ups
- Player dashboard showing assigned gigs and availability status
- Availability tracking with `Available`, `Not Available`, `Unsure yet`, and `Unanswered`
- Account claiming/password reset flow for players added by an admin
- SMTP-based password reset emails

## Requirements

- Linux server
- Python 3.11+ recommended
- `python3-venv`
- `git`
- A reverse proxy such as Nginx is recommended for production

## Quick Start On A New Linux Server

These steps assume:

- the site will live in `/opt/gigplanner`
- the service user will be `gigplanner`
- the site will be served behind Nginx

Adjust paths and usernames if you prefer a different layout.

## 1. Install System Packages

On Ubuntu or Debian:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

## 2. Create A Service User

```bash
sudo useradd --system --create-home --home-dir /opt/gigplanner --shell /usr/sbin/nologin gigplanner
```

If the user already exists, you can skip this step.

## 3. Copy The Application To The Server

Using git:

```bash
sudo -u gigplanner git clone https://your-repository-url /opt/gigplanner/app
```

Or copy the project files manually into:

```text
/opt/gigplanner/app
```

## 4. Create A Virtual Environment

```bash
cd /opt/gigplanner/app
sudo -u gigplanner python3 -m venv venv
sudo -u gigplanner ./venv/bin/pip install --upgrade pip
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
```

## 5. Create A Production Environment File

Create `/opt/gigplanner/app/.env`:

```bash
sudo -u gigplanner nano /opt/gigplanner/app/.env
```

Suggested contents:

```env
SECRET_KEY=replace-this-with-a-long-random-secret

SMTP_SERVER=localhost
SMTP_PORT=25
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false

MAIL_FROM=noreply@gigplanner.uk
BASE_URL=https://gigplanner.uk
PASSWORD_RESET_MAX_AGE=86400
```

Notes:

- `SECRET_KEY` must be changed for production.
- `SMTP_SERVER=localhost` with blank username/password works for a local mail relay.
- `BASE_URL` should be the public URL users will click in password reset emails.
- `PASSWORD_RESET_MAX_AGE` is the reset link lifetime in seconds. `86400` = 24 hours.

## 6. Confirm File Ownership

```bash
sudo chown -R gigplanner:gigplanner /opt/gigplanner
```

## 7. Test The App Manually

Before setting up a service, test that the app starts:

```bash
cd /opt/gigplanner/app
set -a
. ./.env
set +a
./venv/bin/python app.py
```

By default Flask will listen on:

```text
http://127.0.0.1:5000
```

Stop it with `Ctrl+C` once you confirm it starts.

## 8. Create A systemd Service

Create `/etc/systemd/system/gigplanner.service`:

```ini
[Unit]
Description=Gig Planner Flask App
After=network.target

[Service]
User=gigplanner
Group=gigplanner
WorkingDirectory=/opt/gigplanner/app
EnvironmentFile=/opt/gigplanner/app/.env
ExecStart=/opt/gigplanner/app/venv/bin/flask --app app run --host 127.0.0.1 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gigplanner
sudo systemctl start gigplanner
sudo systemctl status gigplanner
```

To view logs:

```bash
sudo journalctl -u gigplanner -f
```

## 9. Configure Nginx

Create `/etc/nginx/sites-available/gigplanner`:

```nginx
server {
    listen 80;
    server_name gigplanner.uk www.gigplanner.uk;

    location /static/ {
        alias /opt/gigplanner/app/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/gigplanner /etc/nginx/sites-enabled/gigplanner
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Add HTTPS

If you use Let's Encrypt:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gigplanner.uk -d www.gigplanner.uk
```

After HTTPS is configured, update:

```env
BASE_URL=https://gigplanner.uk
```

if it is not already set.

## Database

The app uses a SQLite database file:

```text
gigplanner.db
```

It is created automatically in the application directory the first time the app starts.

Important notes:

- keep regular backups of `gigplanner.db`
- the SQLite file must be writable by the service user
- if you restore a backup, stop the service first

Example backup:

```bash
cd /opt/gigplanner/app
cp gigplanner.db gigplanner.db.backup-$(date +%F-%H%M%S)
```

## Account Claiming And Password Reset

When a band admin adds a new player by email:

- if the email already exists, the existing user account is reused
- if the email does not exist, a new user record is created with no password

That user can then claim the account by using `Reset your password` on the login page.

The reset email:

- comes from `noreply@gigplanner.uk` by default
- links back to `gigplanner.uk` by default
- tells users they can contact `contact@gigplanner.uk` if they have problems

## Updating The Site

To deploy a new version:

```bash
cd /opt/gigplanner/app
sudo -u gigplanner git pull
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
sudo systemctl restart gigplanner
```

Then check:

```bash
sudo systemctl status gigplanner
sudo journalctl -u gigplanner -n 100
```

## Common Configuration Variables

Environment variables supported by the app:

- `SECRET_KEY`
- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `MAIL_FROM`
- `BASE_URL`
- `PASSWORD_RESET_MAX_AGE`

## Troubleshooting

### Password reset emails are not arriving

Check:

- the SMTP host and port are correct
- the server can connect to the SMTP server
- authentication details are correct if required
- mail is not being blocked by a firewall or provider

Useful checks:

```bash
sudo journalctl -u gigplanner -f
```

### The site starts but pages fail

Check the service logs:

```bash
sudo journalctl -u gigplanner -n 200
```

### Static files are missing

Check:

- Nginx `alias` path points to `/opt/gigplanner/app/static/`
- file ownership allows Nginx to read the files

## Development

For local development:

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python app.py
```

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python app.py
```
