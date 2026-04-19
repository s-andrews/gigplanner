# Deploying Gig Planner on AWS

This guide explains how to deploy Gig Planner on AWS, including:

- hosting the application
- DNS and HTTPS
- outbound email for password reset and account claiming

It assumes:

- you already have an AWS account
- your domain is already registered
- you control the DNS records for the domain
- the application code is available in this repository

Because Gig Planner currently uses SQLite, it is best deployed as a single application host.

## Two Supported AWS Deployment Patterns

This application can be deployed on AWS in two sensible ways.

### Option 1: Single Amazon Lightsail instance exposed directly to the internet

Use this if:

- you will only run one application server
- you want the simplest and lowest-cost setup
- you are happy to terminate HTTPS directly on the server

Typical stack:

- Amazon Lightsail instance
- Lightsail static IP
- Nginx
- Gunicorn
- Lightsail DNS zone, Route 53, or external DNS
- Let's Encrypt for TLS
- Amazon SES for email

Traffic flow:

```text
User -> DNS -> Lightsail instance (Nginx HTTPS) -> Gunicorn -> Flask
```

### Option 2: Single EC2 instance behind an Application Load Balancer

Use this if:

- you want cleaner AWS-native HTTPS termination
- you want to use ACM for certificates
- you may want easier future scaling later
- you are comfortable paying for an ALB

Typical stack:

- Amazon EC2
- Amazon EBS
- Nginx
- Gunicorn
- Application Load Balancer
- AWS Certificate Manager
- Route 53 or external DNS
- Amazon SES for email

Traffic flow:

```text
User -> DNS -> ALB (HTTPS) -> EC2 (HTTP) -> Gunicorn -> Flask
```

## Which Option Should You Choose?

For this app as it exists today, the recommended default is:

- `Single Amazon Lightsail instance exposed directly to the internet`

Reasons:

- the app uses SQLite, so there is no benefit to horizontal scaling right now
- it is cheaper
- it is simpler to operate
- it avoids the cost and complexity of an ALB

Choose the ALB option if:

- you specifically want ACM-managed certificates
- you want a more AWS-standard edge architecture
- you expect to evolve the app architecture later

## Shared AWS Services

Both deployment options use the same core AWS services:

- `Amazon SES` for outbound email
- `Amazon Route 53` optionally for DNS hosting
- `IAM` for access control
- `CloudWatch` optionally for monitoring

For the single-server option, use:

- `Amazon Lightsail` for the app host
- Lightsail instance disk storage
- Lightsail static IP

Only the load-balanced option additionally uses:

- `Amazon EC2`
- `Amazon EBS`
- `Application Load Balancer`
- `AWS Certificate Manager`

## Important Application Note

The app currently uses:

- Flask
- SQLite (`gigplanner.db`)
- SMTP environment variables for sending email

Because the database is SQLite:

- deploy one application instance only
- do not run multiple EC2 app hosts unless you first move to a shared database such as Amazon RDS

## DNS Strategy

You have two main choices for DNS.

### Use Route 53 for DNS hosting

This is often the easiest AWS-centric option.

You can:

- create a public hosted zone in Route 53
- update your registrar to use the Route 53 name servers

This works even if the domain was registered somewhere other than AWS.

### Keep DNS with the current provider

This also works.

You can still use:

- SES domain verification
- SES DKIM
- ACM DNS validation for the ALB option

but you must add the required DNS records manually at your current DNS provider.

## Choose An AWS Region

Pick one AWS Region and keep the application services together there.

Recommended to keep in the same Region:

- EC2
- SES
- ALB if used
- ACM certificate for the ALB if used

Notes:

- SES SMTP credentials are region-specific
- ACM public certificates for an ALB must be created in the same Region as the ALB

## Networking

For the Lightsail option:

- Lightsail handles the underlying networking for the instance
- you mainly work with the Lightsail firewall, static IP, and DNS settings

For the EC2 + ALB option you need:

- a VPC
- at least one public subnet
- an Internet Gateway
- route tables allowing internet access

Because this is a single-host deployment, a simple network layout is enough in either case.

## Security Groups

### Lightsail option

Use the Lightsail networking/firewall rules.

Allow inbound:

- TCP 22 from your admin IP only
- TCP 80 from anywhere
- TCP 443 from anywhere

Allow outbound:

- general internet access for package installs and SES SMTP

### EC2 + ALB option

Create two security groups.

ALB security group inbound:

- TCP 80 from `0.0.0.0/0`
- TCP 443 from `0.0.0.0/0`

ALB security group outbound:

- all traffic to the EC2 security group

EC2 security group inbound:

- TCP 22 from your admin IP only
- TCP 80 from the ALB security group

EC2 security group outbound:

- all traffic, or at least internet access for updates and SES SMTP

## Option 1: Lightsail Single-Server Deployment

This is the recommended option for this app today.

### Create The Lightsail Instance

In Lightsail:

- create a Linux instance
- choose a current LTS or supported distribution image
- pick a small plan suitable for Flask + SQLite

A typical starting point is a small Linux instance with enough disk for:

- the app code
- `gigplanner.db`
- logs
- backups

### Attach A Static IP

After creating the Lightsail instance:

- allocate a Lightsail static IP
- attach it to the instance

This is important because the default public IP can change when the instance is stopped and started.

### Lightsail Firewall

In the Lightsail networking/firewall settings, allow:

- TCP 22 from your admin IP only
- TCP 80 from anywhere
- TCP 443 from anywhere

### Install The Application On Lightsail

SSH into the instance and install dependencies.

On a typical Linux image:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx
```

If you use an Amazon Linux based image instead:

```bash
sudo dnf update -y
sudo dnf install -y git python3 python3-pip nginx
python3 -m venv --help >/dev/null || sudo dnf install -y python3-virtualenv
```

Create the service user:

```bash
sudo useradd --system --create-home --home-dir /opt/gigplanner --shell /sbin/nologin gigplanner
```

Clone or copy the application:

```bash
sudo -u gigplanner git clone https://your-repository-url /opt/gigplanner/app
cd /opt/gigplanner/app
sudo -u gigplanner python3 -m venv venv
sudo -u gigplanner ./venv/bin/pip install --upgrade pip
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
sudo -u gigplanner ./venv/bin/pip install gunicorn
```

### Lightsail DNS

You have three valid DNS approaches for the Lightsail option:

- use a Lightsail DNS zone
- use Route 53
- keep your existing external DNS provider

If you use Lightsail DNS:

- create a DNS zone for the domain in Lightsail
- point the domain registrar to the Lightsail name servers
- create `A` records pointing to the Lightsail static IP

If you use Route 53:

- create a hosted zone in Route 53
- point the registrar to Route 53 name servers
- create `A` records pointing to the Lightsail static IP

If you keep external DNS:

- create `A` records for the root domain and `www` pointing to the Lightsail static IP

### HTTPS On Lightsail

For the single Lightsail server option, use Let's Encrypt on the instance.

Install certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

or on Amazon Linux based images:

```bash
sudo dnf install -y certbot python3-certbot-nginx
```

Configure Nginx first for HTTP:

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
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then request the certificate:

```bash
sudo certbot --nginx -d gigplanner.uk -d www.gigplanner.uk
```

This will configure Nginx for HTTPS and redirect HTTP to HTTPS.

### Pros Of Lightsail

- simpler than EC2 + ALB
- lower cost
- a strong fit for a small single-host Flask app
- static IP support is built in

### Cons Of Lightsail

- less flexible than the full EC2 + ALB architecture
- not the best fit if you later need multiple app servers
- ACM/ALB style TLS termination is not part of this path

## Option 2: EC2 Behind An Application Load Balancer

## EC2 Instance Setup

Suggested starting point:

- Amazon Linux 2023 or Ubuntu 24.04 LTS
- `t3.small` or `t3.medium`
- 20 GB or more gp3 EBS

Create the instance, attach the correct security group, and SSH in.

Install dependencies on Amazon Linux 2023:

```bash
sudo dnf update -y
sudo dnf install -y git python3 python3-pip nginx
python3 -m venv --help >/dev/null || sudo dnf install -y python3-virtualenv
```

Create a service user:

```bash
sudo useradd --system --create-home --home-dir /opt/gigplanner --shell /sbin/nologin gigplanner
```

Clone or copy the application:

```bash
sudo -u gigplanner git clone https://your-repository-url /opt/gigplanner/app
cd /opt/gigplanner/app
sudo -u gigplanner python3 -m venv venv
sudo -u gigplanner ./venv/bin/pip install --upgrade pip
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
sudo -u gigplanner ./venv/bin/pip install gunicorn
```

## Application Configuration

Create `/opt/gigplanner/app/.env`:

```env
SECRET_KEY=replace-this-with-a-long-random-secret

SMTP_SERVER=email-smtp.eu-west-2.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=replace-with-ses-smtp-username
SMTP_PASSWORD=replace-with-ses-smtp-password
SMTP_USE_TLS=true

MAIL_FROM=noreply@gigplanner.uk
BASE_URL=https://gigplanner.uk
PASSWORD_RESET_MAX_AGE=86400
```

Adjust:

- `SMTP_SERVER` for the SES Region you use
- `BASE_URL` to the public application URL

Then fix ownership:

```bash
sudo chown -R gigplanner:gigplanner /opt/gigplanner
```

## Run The App With systemd

Create `/etc/systemd/system/gigplanner.service`:

```ini
[Unit]
Description=Gig Planner
After=network.target

[Service]
User=gigplanner
Group=gigplanner
WorkingDirectory=/opt/gigplanner/app
EnvironmentFile=/opt/gigplanner/app/.env
ExecStart=/opt/gigplanner/app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gigplanner
sudo systemctl start gigplanner
sudo systemctl status gigplanner
```

## Nginx Setup

For both deployment options, Nginx should reverse proxy to Gunicorn.

For the Lightsail option, Nginx should listen on HTTP and HTTPS.

For the ALB option, Nginx can listen on HTTP only.

This is the more AWS-native HTTPS setup.

### Nginx On EC2

For the ALB option, Nginx can listen on port 80 only:

```nginx
server {
    listen 80;
    server_name _;

    location /static/ {
        alias /opt/gigplanner/app/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable Nginx:

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

### Target Group

Create an ALB target group:

- target type: `instance`
- protocol: `HTTP`
- port: `80`
- health check path: `/`

Register the EC2 instance in the target group.

### Application Load Balancer

Create an internet-facing ALB:

- listeners on `80` and `443`
- public subnets
- ALB security group

Configure:

- HTTP 80 redirects to HTTPS 443
- HTTPS 443 forwards to the target group

### ACM Certificate

Request a public ACM certificate in the same Region as the ALB for:

- `gigplanner.uk`
- optionally `www.gigplanner.uk`

Use DNS validation.

If you use Route 53:

- ACM can usually create the validation records automatically

If you use external DNS:

- manually create the ACM validation CNAME records

Once issued, attach the certificate to the ALB HTTPS listener.

### DNS For The ALB Option

Point DNS at the ALB:

- in Route 53 use an alias `A` record
- with an external DNS provider use the provider's supported ALIAS/ANAME/CNAME-at-apex feature if available

### Pros Of The ALB Option

- ACM-managed certificates
- cleaner AWS HTTPS termination
- easier path to future scaling
- more AWS-standard edge architecture

### Cons Of The ALB Option

- higher cost
- more moving parts
- more complexity for a single-instance app

## Amazon SES Setup

The app sends password reset and account-claim emails using SMTP, so Amazon SES is a good fit for both deployment options.

### 1. Verify Your Domain

In Amazon SES:

- choose your Region
- create a verified identity for `gigplanner.uk`

SES will give you DNS records to add, typically:

- TXT verification record
- DKIM CNAME records

Add them in Route 53 or your current DNS provider.

### 2. Move Out Of Sandbox

New SES accounts start in the sandbox.

While in sandbox:

- you can only send to verified recipients
- sending volume is heavily limited

Request production access in the same Region as your SES SMTP endpoint.

### 3. Create SMTP Credentials

In SES:

- create SMTP credentials
- note the username and password

Then set the app environment values:

```env
SMTP_SERVER=email-smtp.<region>.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
MAIL_FROM=noreply@gigplanner.uk
```

### 4. Improve Deliverability

Recommended DNS records:

- SES verification
- DKIM
- SPF
- DMARC

Example SPF:

```text
v=spf1 include:amazonses.com ~all
```

Example DMARC:

```text
v=DMARC1; p=none; rua=mailto:contact@gigplanner.uk
```

## Testing

After the app is online:

1. open the site over HTTPS
2. log in as an existing user
3. test the dashboard and calendar feed
4. test `Reset your password`
5. confirm the email arrives and the reset flow works

If email fails, check:

- app logs
- SES identity verification
- sandbox status
- SMTP username/password
- SMTP endpoint Region

## Persistence And Backups

The app stores data in:

```text
gigplanner.db
```

Because that file is local to the application host:

- use persistent Lightsail instance storage or EBS-backed EC2 storage, depending on the option you choose
- take regular snapshots
- back up before deployments

Manual backup example:

```bash
cd /opt/gigplanner/app
cp gigplanner.db gigplanner.db.backup-$(date +%F-%H%M%S)
```

## Monitoring And Operations

Recommended:

- CloudWatch or Lightsail instance monitoring
- CloudWatch alarm on CPU
- snapshot schedule
- CloudWatch alarm on ALB unhealthy targets if using the ALB option

Useful commands:

```bash
sudo systemctl status gigplanner
sudo systemctl status nginx
sudo journalctl -u gigplanner -f
```

## Updating The Application

```bash
cd /opt/gigplanner/app
sudo -u gigplanner git pull
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
sudo -u gigplanner ./venv/bin/pip install gunicorn
sudo systemctl restart gigplanner
sudo systemctl reload nginx
```

Then verify:

```bash
sudo systemctl status gigplanner
sudo nginx -t
```

## Cost Guidance

### Lightsail option

Main AWS costs:

- Lightsail instance plan
- Lightsail static IP
- snapshots
- SES
- optional Route 53 or Lightsail DNS

This is the cheaper option.

### ALB option

Main AWS costs:

- EC2
- EBS
- ALB
- Route 53 if used
- SES
- snapshots

This is more expensive but gives a cleaner AWS edge setup.

## Recommended Choice For This App Today

For Gig Planner in its current form, the most practical AWS deployment is:

- `single Amazon Lightsail instance directly exposed to the internet`
- `Nginx + Gunicorn on the instance`
- `Let's Encrypt for HTTPS`
- `Amazon SES for email`

That is the best balance of:

- simplicity
- cost
- suitability for SQLite

If the app later moves to RDS and multiple app instances, revisit the ALB-based option.

## AWS Documentation Used

This guide aligns with the AWS documentation for:

- ACM DNS validation:
  https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-validate-dns.html
- ACM domain ownership validation:
  https://docs.aws.amazon.com/acm/latest/userguide/domain-ownership-validation.html
- SES SMTP credentials:
  https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html
- SES verified identities:
  https://docs.aws.amazon.com/ses/latest/dg/verify-addresses-and-domains.html
- SES production access:
  https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html
- Route 53 with external DNS or hosted zones:
  https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/creating-migrating.html
- ALB target groups:
  https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html
