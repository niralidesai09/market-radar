#!/bin/bash
# One-time setup: stores your private keys as GitHub Secrets (never in code).
set -e
REPO="${1:?usage: ./setup.sh owner/repo}"
ask() { printf "\n%s\n> " "$1"; if [ "$3" = "hide" ]; then read -rs v; echo; else read -r v; fi; printf '%s' "$v" | gh secret set "$2" --repo "$REPO"; echo "saved $2"; }
ask "1/5  Paste your GEMINI API key (typing is hidden):" GEMINI_API_KEY hide
ask "2/5  The Gmail address that will SEND the emails:" GMAIL_USER
ask "3/5  That Gmail's 16-letter App Password (hidden; spaces are fine):" GMAIL_APP_PASSWORD hide
ask "4/5  The email address that should RECEIVE the briefings:" MAIL_TO
TOPIC="radar-$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 16)"
printf '%s' "$TOPIC" | gh secret set NTFY_TOPIC --repo "$REPO"
echo; echo "5/5  Phone alerts: install the free 'ntfy' app, tap +, and subscribe to this topic name:"; echo; echo "     $TOPIC"; echo
