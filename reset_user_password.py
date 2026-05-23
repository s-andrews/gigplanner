import argparse
import getpass
import sqlite3
import sys

from werkzeug.security import generate_password_hash

from app import DATABASE, init_db, validate_password_complexity


def parse_args():
    parser = argparse.ArgumentParser(
        description="Set a user's password immediately by email address."
    )
    parser.add_argument("email", help="Email address of the user to update")
    parser.add_argument(
        "--password",
        help="New password. If omitted, you will be prompted securely.",
    )
    return parser.parse_args()


def prompt_for_password():
    password = getpass.getpass("New password: ")
    confirm_password = getpass.getpass("Confirm new password: ")
    if password != confirm_password:
        raise ValueError("The passwords do not match.")
    return password


def main():
    args = parse_args()
    email = args.email.strip().lower()
    if not email:
        print("Email is required.", file=sys.stderr)
        return 1

    try:
        password = args.password if args.password is not None else prompt_for_password()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    password_error = validate_password_complexity(password)
    if password_error:
        print(password_error, file=sys.stderr)
        return 1

    init_db()
    db = sqlite3.connect(DATABASE)
    try:
        user = db.execute(
            "SELECT id, email, name FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if user is None:
            print(f"No user found with email {email}.", file=sys.stderr)
            return 1

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user[0]),
        )
        db.commit()
    finally:
        db.close()

    print(f"Password updated for {user[2]} <{user[1]}>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
