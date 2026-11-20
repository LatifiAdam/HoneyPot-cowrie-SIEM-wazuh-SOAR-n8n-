# GitHub publishing checklist

Work through this before the first push and again before making the repository public. Run the commands from the repository root.

## Recommended public repository contents

- `README.md` with architecture, detection logic, runbook and evidence gallery.
- `docs/`: setup guide, troubleshooting, incident case study, MITRE mapping and this checklist.
- Curated, sanitized screenshots in `screenshots/`.
- Safe Wazuh XML snippets in `config/`.
- `integrations/custom-n8n.py` with no hard-coded secret.
- Sanitized sample events and alerts in `samples/`.
- `n8n/README.md`; add a sanitized workflow export only after reviewing and testing it.

## Before publishing

### 1. Secrets and identifiers in text files

- [ ] Search for secret-shaped values. This should print nothing:

  ```bash
  grep -rnIE "[0-9]{6,}:[A-Za-z0-9_-]{30,}|[A-Fa-f0-9]{32,}|BEGIN [A-Z ]*PRIVATE KEY" \
    --exclude-dir=.git --exclude-dir=screenshots .
  ```

  The first pattern matches Telegram bot tokens, the second long hex secrets such as `openssl rand -hex 32` output, the third private keys.

- [ ] Search for credential keywords and review each hit:

  ```bash
  grep -rnIiE "token|secret|passw|api[_-]?key|chat[_-]?id" --exclude-dir=.git --exclude-dir=screenshots .
  ```

  In this repository most hits are documentation prose, the `X-Wazuh-Token` header name, `REPLACE_WITH_A_NEW_RANDOM_SECRET` and `<redacted-test-password>`. Any hit that looks like a real value needs removing.

- [ ] Search for private addresses and real hostnames:

  ```bash
  grep -rnIE "\b(10\.[0-9]+|192\.168|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]+" \
    --exclude-dir=.git --exclude-dir=screenshots .
  ```

  Documentation-only ranges (`198.51.100.0/24`, `203.0.113.0/24`, `192.0.2.0/24`) are fine. `127.0.0.1` is fine.

- [ ] Confirm the author line in `README.md` is filled in, and decide on a `LICENSE`.

### 2. Screenshots

- [ ] Open every image at full resolution and read **all** of it, including areas partly hidden behind headers, overlays or scrolled-off content. Messages and text behind a chat header or toolbar are easy to miss.
- [ ] Check for IP addresses, hostnames, usernames, passwords, tokens, chat IDs, webhook URLs and bot names that should not be public.
- [ ] Optional second pass with OCR (this catches text that is hard to see by eye):

  ```bash
  for f in screenshots/*.png; do
    echo "== $f"
    tesseract "$f" - 2>/dev/null | grep -nE "([0-9]{1,3}\.){3}[0-9]{1,3}|[0-9]{6,}:[A-Za-z0-9_-]{20,}|token|secret"
  done
  ```

- [ ] Strip image metadata, for example with `exiftool -all= -overwrite_original screenshots/*.png`.
- [ ] Rotate any credential that was ever visible in a screenshot, terminal history or chat.

### 3. Technical validation

- [ ] Validate the XML snippets and the Python script:

  ```bash
  for f in config/*; do xmllint --noout "$f" && echo "ok: $f"; done
  python3 -m py_compile integrations/custom-n8n.py
  for f in samples/*.json; do python3 -m json.tool "$f" > /dev/null && echo "ok: $f"; done
  ```

- [ ] Confirm the Python script contains no secret and that the token is only read from its arguments.
- [ ] Check that every relative link in the Markdown files opens.
- [ ] Confirm that all examples and samples use placeholders or documentation-only values.

### 4. Repository state

- [ ] Review `.gitignore`, then run `git status` and `git diff --cached --stat` and read the list of files about to be committed. Nothing from [Files and data that must stay private](#files-and-data-that-must-stay-private) should appear.
- [ ] Search the whole history, not just the current tree, before making an existing repository public:

  ```bash
  git log -p --all | grep -iE "token|secret|passw|api[_-]?key" | head
  ```

  If a secret was committed at any point, rotate it. Deleting the file in a later commit is not enough.

- [ ] Consider an automated scanner such as `gitleaks` or `trufflehog` as a final check.

## Files and data that must stay private

- `.env` files, passwords, API keys, webhook tokens, Telegram bot tokens and chat IDs.
- Cowrie `userdb.txt`, real JSON logs, real attacker details, password lists and raw captures.
- Wazuh `client.keys`, API credentials, live `ossec.conf`, indexes, databases, queues and log directories.
- n8n database, `.n8n/`, credential store, encryption key, unsanitized workflow exports and execution data.
- Private SSH/TLS keys, VM disks, snapshots, personal downloads and packet captures containing unrelated traffic.

## Important screenshot exclusion

One image in the original capture archive showed a token-like value in a terminal command. That image was intentionally excluded from the public gallery. Do not publish it. If the value was a live credential, rotate it before making the repository public.
