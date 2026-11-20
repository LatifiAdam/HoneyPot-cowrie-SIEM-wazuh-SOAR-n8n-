# SOC case study: repeated SSH authentication failures

## Incident summary

A controlled SSH password-guessing exercise was run from Kali against the Cowrie honeypot. Cowrie recorded failed authentication attempts, Wazuh evaluated the JSON events with custom rules, and the alert pipeline delivered messages to Telegram through the n8n workflow.

| | |
|---|---|
| **Environment** | Isolated home lab |
| **Target** | Ubuntu host running Cowrie on TCP `2222` |
| **Source** | Kali Linux VM (address anonymized as `LAB_ATTACKER_IP` in the evidence) |
| **Activity** | Repeated SSH authentication failures (attempted username `labtester`) |
| **Detection** | Wazuh rules `100501` (level 7) and `100504` (level 12) |
| **Response** | Alert and analyst notification only; no automatic blocking |

## Evidence and event chain

1. **Network access:** Kali reached the Cowrie SSH service on TCP `2222` ([`01`](../screenshots/01-kali-ssh-authentication-test.png)).
2. **Honeypot telemetry:** Cowrie wrote a `cowrie.login.failed` event to `cowrie.json` ([`02`](../screenshots/02-cowrie-json-failed-login.png)).
3. **SIEM detection:** Wazuh rule `100501` (level 7) matched each failed-login event. Rule `100504` (level 12) fires when the configured threshold of failures from one source is reached within the timeframe.
4. **Automation:** the Wazuh `custom-n8n` integration submitted the JSON alert to the authenticated n8n webhook ([`05`](../screenshots/05-n8n-high-low-workflow.png), [`06`](../screenshots/06-n8n-successful-execution.png)).
5. **Triage notification:** n8n evaluated the severity and Telegram received the LOW or HIGH message ([`07`](../screenshots/07-telegram-cowrie-login-failures.png), [`08`](../screenshots/08-telegram-high-bruteforce-alert.png)).

Screenshots `02` and `07` together show the Cowrie event and its corresponding notification. The Telegram messages keep the Cowrie event type and the Wazuh alert timestamp. Screenshot `08` shows the HIGH-severity message format used for rule `100504`.

## Timeline

Times are the `Time:` values of the last three Telegram messages visible in screenshot `07` (UTC, `+0000`).

| Time (UTC, 2026-11-20) | Event | Rule | Level | Route |
|---|---|---|---:|---|
| 00:32:01.684 | Failed SSH login, username `labtester` | `100501` | 7 | LOW |
| 00:32:46.943 | Failed SSH login, same source (+45 s) | `100501` | 7 | LOW |
| 00:33:19.812 | Failed SSH login, same source (+33 s) | `100501` | 7 | LOW |

These three failures span 78 seconds and number fewer than five, so they stay below the `100504` threshold and are all LOW. This illustrates the design: sparse guessing stays at LOW, and only a burst of five failures within 60 seconds crosses the HIGH threshold.

## Detection and severity

| Rule | Condition | Level | Notification |
|---|---|---:|---|
| `100501` | Cowrie failed SSH login | 7 | LOW |
| `100503` | Command entered in the honeypot session | 8 | LOW |
| `100502` | Cowrie successful (simulated) SSH login | 10 | HIGH |
| `100504` | Five failed logins from the same source within 60 seconds | 12 | HIGH |

The n8n severity threshold is `10`. Alerts below it go to the monitoring message; level 10 and above go to the high-priority message.

## Analyst assessment

The activity is consistent with SSH password guessing against an exposed service. Cowrie is an emulated environment, so a successful Cowrie login represents access to the honeypot's simulated shell, not proof that a production host was compromised.

The source, timestamps, attempted username, authentication outcomes and any subsequent commands should be retained as investigation evidence. Repeated failures from one source warrant review of the related session records and any other activity from that source in the lab telemetry.

## Triage playbook

| Alert | Priority | What the analyst does |
|---|---|---|
| `100501` single failure | Low | Note the source and username. No action unless the source repeats. |
| `100504` burst of failures | High | Pivot on the source: other sessions, other usernames, any later success. Record it as a brute-force attempt. |
| `100502` successful login | High | Review the whole session. Find which credentials worked and what the actor did next. |
| `100503` commands entered | Medium–High | Read the commands in order and look for downloads, persistence or lateral-movement attempts. |

Useful queries. Both logs hold one JSON object per line, so `jq` works directly:

```bash
# On the Wazuh Manager: all brute-force alerts with source and username
sudo jq -c 'select(.rule.id=="100504") | {t:.timestamp, ip:.data.src_ip, user:.data.username}' \
  /var/ossec/logs/alerts/alerts.json

# On the honeypot: everything one source did
jq -c 'select(.src_ip=="<SRC_IP>")' /home/cowrie/my-honeypot/var/log/cowrie/cowrie.json

# On the honeypot: a full session by its ID
jq -c 'select(.session=="<SESSION_ID>")' /home/cowrie/my-honeypot/var/log/cowrie/cowrie.json
```

## Recommended response

- Preserve the Cowrie JSON events and corresponding Wazuh alert records.
- Review the session timeline, attempted usernames, authentication outcomes and commands.
- Correlate the source with other available telemetry before drawing conclusions.
- Escalate according to the lab's severity policy when repeated attempts or a successful simulated login are observed.
- Keep containment manual in this project; only consider automated blocking after testing safeguards, allowlists and false-positive handling.

## Detection gaps and next steps

The pipeline only covers the Cowrie events that have a rule. Possible extensions, none of which are implemented:

- **Reconnaissance.** No rule covers `cowrie.session.connect`, so the Nmap scan is not detected as a scan (see the [MITRE mapping](mitre-attack-mapping.md)).
- **Post-login activity.** Events such as `cowrie.session.file_download` are not covered, although downloaded files are often the most valuable honeypot signal.
- **Noise control.** A burst can re-trigger the HIGH rule. Add suppression in Wazuh or de-duplication in n8n.
- **Enrichment.** Add reputation or geolocation lookups for the source address in n8n, using only data that is safe to send to a third party.
- **ATT&CK tagging.** Add `<mitre>` tags to the rules so alerts appear in Wazuh's MITRE views.

## Lessons learned

The exercise demonstrates end-to-end alert visibility from a purpose-built honeypot through SIEM correlation and SOAR-style notification. It also demonstrates why a SOC analyst should distinguish a honeypot event from compromise of a real production system.
