# Deploying Gig Planner on AWS

This guide describes how to deploy Gig Planner on AWS infrastructure, including:

- web hosting
- TLS certificates
- DNS
- email sending for password reset and account claiming

It assumes:

- you already have an AWS account
- your domain is already registered
- you control the DNS records for the domain
- the application code is available in this repository

This guide uses a simple, production-friendly AWS architecture:

- Amazon EC2 for the Flask application
- Amazon EBS for persistent local storage
- Application Load Balancer (ALB) for HTTPS
- AWS Certificate Manager (ACM) for TLS
- Amazon Route 53 for DNS hosting or optional DNS management
- Amazon SES for outbound email

This is a good fit for the current application because it uses SQLite and local file storage rather than a separate managed database.

## Recommended AWS Architecture

For a small single-instance deployment:

- 1 VPC
- 1 public subnet for the load balancer
- 1 public subnet for the EC2 instance
- 1 EC2 instance running Gunicorn and Nginx
- 1 Application Load Balancer terminating HTTPS
- 1 ACM public certificate for the domain
- 1 Route 53 hosted zone or external DNS provider with records pointing into AWS
- 1 SES verified domain for email sending

Traffic flow:

```text
User -> DNS -> ALB (HTTPS) -> EC2 (HTTP) -> Flask/Gunicorn
```

Email flow:

```text
Gig Planner -> Amazon SES SMTP -> recipient mailbox
```

## AWS Services Used

- `Amazon EC2` to run the application
- `Amazon EBS` to persist the SQLite database and app files
- `Elastic Load Balancing / Application Load Balancer` for HTTPS and forwarding to EC2
- `AWS Certificate Manager` for TLS certificates
- `Amazon Route 53` for DNS hosting if you want AWS to host your DNS
- `Amazon SES` for password reset/account claim emails
- `IAM` for access control
- `CloudWatch` optionally for logs and alarms

## Important Application Notes

This app currently uses:

- Flask
- SQLite (`gigplanner.db`)
- SMTP settings from environment variables

Because the database is SQLite:

- this deployment guide is aimed at a single EC2 instance
- do not place multiple app servers behind the load balancer unless you first move to a shared database such as Amazon RDS

## High-Level Deployment Steps

1. Prepare DNS
2. Create a VPC and security groups
3. Launch an EC2 instance
4. Install the app and run it with Gunicorn
5. Create an ALB
6. Request an ACM certificate
7. Point DNS to the ALB
8. Configure SES for outbound email
9. Set environment variables for the app
10. Test the full site and password reset flow

## 1. DNS Strategy

You have two main options:

### Option A: Keep the domain registered elsewhere, but host DNS in Route 53

This is often the easiest AWS setup.

Steps:

- create a public hosted zone in Route 53 for your domain
- copy the Route 53 name servers
- update the domain registrar to use those Route 53 name servers

### Option B: Keep DNS with the current provider

This also works.

You can still use:

- ACM DNS validation
- SES domain verification
- SES DKIM

but you must manually add the required DNS records at your existing DNS provider.

## 2. Choose An AWS Region

Pick one AWS Region and keep the core services together there.

Recommended:

- EC2
- ALB
- ACM certificate for the ALB
- SES SMTP credentials

Note:

- SES SMTP credentials are region-specific
- ACM public certificates for an ALB must be created in the same Region as the ALB

## 3. Create Networking

If you do not already have a VPC for this app:

- create a VPC
- create at least one public subnet
- attach an Internet Gateway
- ensure the subnet route table allows outbound internet access

For a small deployment you can keep the EC2 instance in a public subnet, but restrict access tightly with security groups.

## 4. Security Groups

Create two security groups:

### ALB security group

Allow inbound:

- TCP 80 from `0.0.0.0/0`
- TCP 443 from `0.0.0.0/0`

Allow outbound:

- all traffic to the EC2 security group

### EC2 security group

Allow inbound:

- TCP 22 from your admin IP only
- TCP 80 from the ALB security group

Allow outbound:

- all traffic, or at minimum outbound access to package repositories and SES SMTP endpoints

Do not expose the Flask app directly to the internet.

## 5. Launch The EC2 Instance

Suggested starting point:

- Amazon Linux 2023 or Ubuntu 24.04 LTS
- `t3.small` or `t3.medium`
- 20 GB or more gp3 EBS volume

Assign:

- the EC2 security group
- an IAM role if you want future integration with AWS services

For a simple install, no special IAM permissions are required by the app itself because it uses SMTP rather than the SES API.

## 6. Install The Application On EC2

SSH to the instance and install dependencies.

On Amazon Linux 2023:

```bash
sudo dnf update -y
sudo dnf install -y git python3 python3-pip nginx
python3 -m venv --help >/dev/null || sudo dnf install -y python3-virtualenv
```

Create an app user:

```bash
sudo useradd --system --create-home --home-dir /opt/gigplanner --shell /sbin/nologin gigplanner
```

Clone or copy the app:

```bash
sudo -u gigplanner git clone https://your-repository-url /opt/gigplanner/app
cd /opt/gigplanner/app
sudo -u gigplanner python3 -m venv venv
sudo -u gigplanner ./venv/bin/pip install --upgrade pip
sudo -u gigplanner ./venv/bin/pip install -r requirements.txt
sudo -u gigplanner ./venv/bin/pip install gunicorn
```

## 7. Configure The Application

Create an environment file:

```bash
sudo -u gigplanner nano /opt/gigplanner/app/.env
```

Recommended contents:

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

- `SMTP_SERVER` to the SES SMTP endpoint for your chosen Region
- `BASE_URL` to your public site URL

Make sure the directory is writable by the service user:

```bash
sudo chown -R gigplanner:gigplanner /opt/gigplanner
```

## 8. Run The App With systemd And Gunicorn

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

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gigplanner
sudo systemctl start gigplanner
sudo systemctl status gigplanner
```

## 9. Configure Nginx On EC2

Nginx will proxy requests from port 80 on the instance to Gunicorn on `127.0.0.1:8000`.

Create `/etc/nginx/conf.d/gigplanner.conf`:

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

Then:

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## 10. Create A Target Group

In AWS:

- create an ALB target group
- target type: `instance`
- protocol: `HTTP`
- port: `80`
- health check path: `/`

Register the EC2 instance in that target group.

## 11. Create An Application Load Balancer

Create an internet-facing ALB:

- scheme: `internet-facing`
- listener: `HTTP 80`
- listener: `HTTPS 443`
- subnets: public subnets
- security group: ALB security group

Initially you can have:

- port 80 redirect to 443
- port 443 forward to the target group

## 12. Request An ACM Certificate

Request a public certificate in the same Region as the ALB for:

- `gigplanner.uk`
- `www.gigplanner.uk` if required

Use DNS validation.

If you use Route 53:

- ACM can create validation records automatically if your hosted zone is in the same AWS account and you have permission

If you use another DNS provider:

- manually create the validation CNAME records ACM gives you

Wait for the certificate to become `Issued`, then attach it to the ALB HTTPS listener.

## 13. Point DNS To The ALB

Create DNS records for:

- `gigplanner.uk`
- optionally `www.gigplanner.uk`

If you use Route 53:

- create an `A` alias record pointing at the ALB

If you use external DNS:

- create `CNAME` records for subdomains such as `www`
- for the apex/root domain, use `ALIAS`, `ANAME`, or your provider’s equivalent if supported
- otherwise use the provider’s AWS/ALB apex-record feature if available

Once DNS is live, the app should be reachable via HTTPS.

## 14. Set Up Amazon SES

The app sends password reset / account claim emails using SMTP, so Amazon SES is a good fit.

### 14.1 Verify The Sending Domain

In Amazon SES:

- choose your Region
- create a verified identity for your domain, for example `gigplanner.uk`

SES will give you DNS records to add, usually:

- TXT verification records
- DKIM CNAME records

Add these records in Route 53 or your current DNS provider.

### 14.2 Move SES Out Of Sandbox

By default, a new SES account is in the sandbox.

While in the sandbox:

- you can only send to verified recipients
- sending rates are heavily limited

Request production access in the same SES Region you plan to use.

### 14.3 Create SMTP Credentials

In SES:

- create SMTP credentials
- note the SMTP username and password

Set these in the app `.env` file:

```env
SMTP_SERVER=email-smtp.<region>.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
MAIL_FROM=noreply@gigplanner.uk
```

### 14.4 Recommended DNS For Better Deliverability

Add the SES records for:

- domain verification
- DKIM

Optionally set:

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

Tune these based on your mail policy.

## 15. Test Email Sending

After SES is configured:

1. go to the login page
2. choose `Reset your password`
3. submit a known user email
4. confirm the reset email is delivered
5. follow the link and set a password

If email fails:

- check app logs
- check SES identity verification
- confirm the account is out of sandbox
- confirm the SMTP Region matches the endpoint and credentials

## 16. Persistence And Backups

The app uses SQLite in `gigplanner.db`.

That means:

- the file lives on the EC2 instance
- EBS volume persistence matters
- snapshots are your backup mechanism unless you implement a custom backup job

Minimum recommendations:

- use gp3 EBS
- enable EBS snapshots on a schedule
- take a snapshot before deployments

You can back up manually:

```bash
cd /opt/gigplanner/app
cp gigplanner.db gigplanner.db.backup-$(date +%F-%H%M%S)
```

For stronger resilience, consider:

- moving the database to Amazon RDS in the future
- moving static file assets to S3 if the app grows

## 17. Monitoring And Operations

Recommended AWS operational additions:

- CloudWatch alarm on EC2 instance status checks
- CloudWatch alarm on ALB unhealthy host count
- CloudWatch alarm on CPU usage
- AWS Backup or scheduled EBS snapshots

Useful instance checks:

```bash
sudo systemctl status gigplanner
sudo systemctl status nginx
sudo journalctl -u gigplanner -f
```

## 18. Updating The Application

To deploy a new version:

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

## 19. Cost Notes

The main AWS costs in this design are:

- EC2 instance
- EBS storage and snapshots
- ALB hourly charge plus traffic
- Route 53 hosted zone and DNS queries if you use Route 53
- SES outbound email
- data transfer out

For the smallest low-volume deployment, the ALB may be a meaningful part of the cost. It is still recommended here because:

- ACM certificates attach cleanly to ALB
- HTTPS termination is simpler
- the architecture is cleaner and easier to evolve

## 20. Suggested AWS Build Order

If you want the fastest path to a working deployment, do this in order:

1. choose Region
2. create Route 53 hosted zone or confirm external DNS access
3. launch EC2 and install the app
4. configure Gunicorn and Nginx
5. verify the SES domain and request SES production access
6. request ACM certificate and complete DNS validation
7. create target group and ALB
8. point DNS at the ALB
9. update `.env` with final `BASE_URL` and SES SMTP settings
10. test site login, reset password, and calendar feed links

## 21. Future Improvements

If the site grows, the next AWS improvements would be:

- move from SQLite to Amazon RDS PostgreSQL
- store secrets in AWS Systems Manager Parameter Store or AWS Secrets Manager
- use Auto Scaling
- place EC2 in private subnets and ALB in public subnets
- ship logs to CloudWatch Logs
- use Amazon CloudFront in front of the ALB if needed

## AWS Documentation Used

This guide aligns with the AWS services and workflows described in:

- ACM DNS validation:
  https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-validate-dns.html
- ACM domain ownership validation:
  https://docs.aws.amazon.com/acm/latest/userguide/domain-ownership-validation.html
- SES SMTP credentials:
  https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html
- SES verified identities:
  https://docs.aws.amazon.com/ses/latest/dg/verify-addresses-and-domains.html
- SES production access / sandbox:
  https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html
- Route 53 subdomain / external DNS usage:
  https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/creating-migrating.html
- ALB target groups:
  https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html
