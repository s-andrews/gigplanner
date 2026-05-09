import argparse
import os
import socket
import smtplib
import ssl
import sys
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage

from dotenv import load_dotenv


def load_config():
    load_dotenv()
    return {
        "SMTP_SERVER": os.environ.get("SMTP_SERVER", "localhost"),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "25")),
        "SMTP_USERNAME": os.environ.get("SMTP_USERNAME", ""),
        "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
        "SMTP_USE_TLS": os.environ.get("SMTP_USE_TLS", "").lower() in {"1", "true", "yes"},
        "MAIL_FROM": os.environ.get("MAIL_FROM", "noreply@gigplanner.uk"),
    }


def mask_secret(value):
    if not value:
        return "<empty>"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def build_message(sender, recipient):
    now = datetime.now(timezone.utc)
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()

    message = EmailMessage()
    message["Subject"] = "Gig Planner SMTP test"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                "This is a Gig Planner SMTP test email.",
                "",
                f"Sent at: {now.isoformat()}",
                f"Hostname: {hostname}",
                f"FQDN: {fqdn}",
            ]
        )
    )
    return message


def print_config(config, recipient):
    print("== SMTP Test Configuration ==")
    print(f"Recipient: {recipient}")
    print(f"From: {config['MAIL_FROM']}")
    print(f"Server: {config['SMTP_SERVER']}")
    print(f"Port: {config['SMTP_PORT']}")
    print(f"Use STARTTLS: {config['SMTP_USE_TLS']}")
    print(f"Username: {mask_secret(config['SMTP_USERNAME'])}")
    print(f"Password: {mask_secret(config['SMTP_PASSWORD'])}")
    print(f"Local hostname: {socket.gethostname()}")
    print(f"Local FQDN: {socket.getfqdn()}")
    print()

    if config["SMTP_PORT"] == 465 and config["SMTP_USE_TLS"]:
        print("Warning: port 465 usually expects implicit SSL, but this script will use SMTP + STARTTLS to match app.py.")
        print()


def resolve_server(hostname):
    print("== DNS Resolution ==")
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except Exception:
        print("DNS lookup failed.")
        raise

    unique_addresses = []
    for entry in resolved:
        address = entry[4][0]
        if address not in unique_addresses:
            unique_addresses.append(address)
    for address in unique_addresses:
        print(f"Resolved address: {address}")
    print()


def send_test_email(config, recipient):
    message = build_message(config["MAIL_FROM"], recipient)

    print("== SMTP Session ==")
    print("Opening SMTP connection...")
    with smtplib.SMTP(config["SMTP_SERVER"], config["SMTP_PORT"], timeout=30) as smtp:
        smtp.set_debuglevel(1)

        print("Connection opened.")
        print("Sending EHLO...")
        code, response = smtp.ehlo()
        print(f"EHLO response: {code} {response!r}")

        if config["SMTP_USE_TLS"]:
            print("Attempting STARTTLS...")
            context = ssl.create_default_context()
            code, response = smtp.starttls(context=context)
            print(f"STARTTLS response: {code} {response!r}")

            print("Sending EHLO again after STARTTLS...")
            code, response = smtp.ehlo()
            print(f"Post-STARTTLS EHLO response: {code} {response!r}")

        if config["SMTP_USERNAME"]:
            print("Attempting SMTP login...")
            code, response = smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            print(f"Login response: {code} {response!r}")
        else:
            print("Skipping SMTP login because SMTP_USERNAME is empty.")

        print("Sending message...")
        send_result = smtp.send_message(message)
        print(f"send_message result: {send_result!r}")
        print("SMTP send completed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Send a debug SMTP test email using Gig Planner settings.")
    parser.add_argument("recipient", help="Email address to receive the test email")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    print_config(config, args.recipient)
    resolve_server(config["SMTP_SERVER"])

    try:
        send_test_email(config, args.recipient)
    except Exception as exc:
        print()
        print("== FAILURE ==")
        print(f"{type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    print()
    print("== SUCCESS ==")
    print("Test email sent successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
