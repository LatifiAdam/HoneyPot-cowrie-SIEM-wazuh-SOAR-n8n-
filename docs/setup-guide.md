# Setup guide

A step-by-step runbook for rebuilding the Cowrie → Wazuh → n8n → Telegram pipeline. Each step ends with a **Verify** check, so a failure is caught at the stage that caused it rather than at the Telegram end of the chain.

> Lab use only. Keep Cowrie, the Wazuh Dashboard and the n8n webhook off the public Internet. Use placeholders such as `<COWRIE_LAB_IP>` in anything you publish.

- [Prerequisites](#prerequisites)
- [Network and ports](#network-and-ports)
- [Step 1 — Cowrie JSON logging](#step-1--cowrie-json-logging)
- [Step 2 — Wazuh Agent on the honeypot](#step-2--wazuh-agent-on-the-honeypot)
- [Step 3 — Custom detection rules](#step-3--custom-detection-rules)
- [Step 4 — Manager integration](#step-4--manager-integration)
- [Step 5 — n8n workflow](#step-5--n8n-workflow)
- [Step 6 — End-to-end test](#step-6--end-to-end-test)
- [Operational notes](#operational-notes)

## Prerequisites

| Component | Needed for | Notes |
|---|---|---|
| Wazuh Manager, Indexer, Dashboard (4.x) | Detection and alert storage | The rule and integration features used here are standard Wazuh 4.x. Record your exact version in your own notes. |
| Wazuh Agent on the Cowrie host | Log forwarding | Must be enrolled and **Active** before Step 3. |
| Cowrie with JSON logging | Event source | The default JSON log is `var/log/cowrie/cowrie.json` under the Cowrie install directory. |
| n8n | SOAR workflow | The screenshots show the n8n 2.x editor, where the button is **Publish**. Older versions call it **Activate**. |
| Telegram bot and chat | Notifications | Create the bot with BotFather, then send it `/start` from the receiving chat. |
| `jq`, `openssl`, `curl`, `python3` | Testing | The integration script uses only the Python standard library. |

## Network and ports

| Flow | Port | Notes |
|---|---|---|
| Test client → Cowrie | TCP `2222` | Cowrie's default SSH emulation port in this lab. |
| Wazuh Agent → Manager | TCP `1514` (events), TCP `1515` (enrolment) | Wazuh defaults. |
| Wazuh Manager → n8n | TCP `5678` | n8n default. `127.0.0.1` works only if n8n runs on the same host as the Manager. |
| Analyst → Wazuh Dashboard | TCP `443` | Wazuh default. Keep it on the lab network. |
| n8n → Telegram | outbound HTTPS `443` | Needs access to `api.telegram.org`. |

## Step 1 — Cowrie JSON logging

On the honeypot, confirm Cowrie is running and writing one JSON object per line:

```bash
tail -n 1 /home/cowrie/my-honeypot/var/log/cowrie/cowrie.json | jq .
```

**Verify:** the output is valid JSON with an `eventid` field. If the file is empty, make one SSH attempt against port `2222` first.

## Step 2 — Wazuh Agent on the honeypot

1. Back up `/var/ossec/etc/ossec.conf`, then merge the element from [`config/cowrie-agent-localfile.xml`](../config/cowrie-agent-localfile.xml) **inside** the existing `<ossec_config>` block. Adjust the path to your Cowrie install.
2. Restart the agent: `sudo systemctl restart wazuh-agent`

**Verify (honeypot):** the log collector announces the file.

```bash
sudo grep -i "analyzing file" /var/ossec/logs/ossec.log | grep cowrie
```

**Verify (Manager):** `sudo /var/ossec/bin/agent_control -l` lists the honeypot as **Active**.

## Step 3 — Custom detection rules

1. On the Manager, back up `/var/ossec/etc/rules/local_rules.xml`, then merge [`config/local_rules.xml`](../config/local_rules.xml) into it. Custom rule IDs must be unique, so check that `100501`–`100504` are free first.
2. Check the configuration: `sudo /var/ossec/bin/wazuh-analysisd -t`
3. Test with `wazuh-logtest`. The sample event is pretty-printed, so flatten it to the single line the tool expects:

   ```bash
   jq -c . samples/cowrie-login-failed.example.json
   sudo /var/ossec/bin/wazuh-logtest
   # paste the one-line JSON at the prompt
   ```

   **Expected:** the final phase reports rule `100501`, level `7`.
4. To test the correlation rule, paste the same line repeatedly **in the same logtest session** and note on which submission rule `100504` (level `12`) first fires. It should fire at the configured threshold of five within 60 seconds. Confirm the exact count on your Wazuh version rather than assuming it.
5. Apply: `sudo systemctl restart wazuh-manager`

**Verify:** make a real failed SSH attempt against Cowrie, then run:

```bash
sudo jq -c 'select(.rule.id=="100501") | {t:.timestamp, ip:.data.src_ip, user:.data.username}' /var/ossec/logs/alerts/alerts.json | tail -n 3
```

## Step 4 — Manager integration

1. Install the script. Wazuh requires it in `/var/ossec/integrations/`, named exactly like the `<name>` in the config, owned by `root:wazuh` with mode `750`:

   ```bash
   sudo install -o root -g wazuh -m 750 integrations/custom-n8n.py /var/ossec/integrations/custom-n8n
   ```

2. Generate a fresh secret and keep it for Step 5. Do not reuse a secret that has appeared in a screenshot, shell history or chat.

   ```bash
   openssl rand -hex 32
   ```

3. Merge [`config/manager-integration.xml.example`](../config/manager-integration.xml.example) inside the Manager's `<ossec_config>`, replacing `REPLACE_WITH_A_NEW_RANDOM_SECRET` with the generated value. Restart: `sudo systemctl restart wazuh-manager`

How the block behaves:

| Setting | Value | Effect |
|---|---|---|
| `<name>` | `custom-n8n` | Wazuh runs `/var/ossec/integrations/custom-n8n`. Custom integration names must start with `custom-`. |
| `<hook_url>` | n8n **production** webhook URL | Passed to the script as argument 3. |
| `<api_key>` | shared secret | Passed as argument 2 and sent as the `X-Wazuh-Token` header. |
| `<level>` | `7` | Forwards alerts at level 7 and above. All four lab rules are at or above 7, so all of them are forwarded. |
| `<alert_format>` | `json` | Required so the script receives JSON. |

**Script contract.** Wazuh calls the script as `custom-n8n <alert-file> <api-key> <hook-url>`. Exit code `0` means the webhook answered 2xx, `1` means an HTTP or network error, and `2` means a usage or configuration error such as a missing file or a non-HTTP URL.

**Verify without waiting for a real alert.** Put n8n in test mode (Step 5), then:

```bash
cp samples/wazuh-alert-100504.example.json /tmp/alert-test.json
sudo /var/ossec/integrations/custom-n8n /tmp/alert-test.json "<TOKEN>" \
  "http://127.0.0.1:5678/webhook-test/wazuh-cowrie-alert"
# expected: n8n webhook returned HTTP 200
```

## Step 5 — n8n workflow

Build the workflow from [`n8n/README.md`](../n8n/README.md): node settings, field mapping, the severity condition and the Telegram message templates. Use the same secret in the Header Auth credential, then **Publish** the workflow so the production URL `/webhook/wazuh-cowrie-alert` is live.

**Verify:** the curl test in the n8n README returns HTTP 200 and an execution appears on the **Executions** page.

## Step 6 — End-to-end test

From the test client, generate a few failed logins, then a burst, against the honeypot:

```bash
nmap -sV -p 2222 <COWRIE_LAB_IP>
ssh -p 2222 <HONEYPOT_USER>@<COWRIE_LAB_IP>
```

Correlate one event across every stage:

| Stage | Where to look | Expect |
|---|---|---|
| Cowrie | `cowrie.json` on the honeypot | `cowrie.login.failed` events |
| Wazuh Agent | Agent shows **Active** in Manager | Events flowing |
| Wazuh rules | `/var/ossec/logs/alerts/alerts.json` | Rule `100501` (level 7); `100504` (level 12) on a burst |
| Integration | `/var/ossec/logs/integrations.log` | No errors |
| n8n | **Executions** page | Success; `true` branch for level ≥ 10, `false` branch otherwise |
| Telegram | Bot chat | A LOW message per failed login, a HIGH message for the burst |

If a stage is empty, use [`troubleshooting.md`](troubleshooting.md).

## Operational notes

- **Token exposure.** Wazuh passes `api_key` to the script as a command-line argument, so it is briefly visible in the process list on the Manager host. Restrict local shell access to that host and never reuse the token elsewhere.
- **Transport.** The integration uses plain HTTP to `127.0.0.1` in the lab. If n8n runs on another host, put it behind HTTPS before sending alerts across a network.
- **Alert volume.** Every failed login produces a LOW alert, and a sustained attack can keep re-triggering the HIGH rule. Consider Wazuh's rule-level `ignore` option or de-duplication in n8n before leaving this running unattended.
- **Attacker-controlled text.** Usernames and commands in alerts come from whoever is attacking the honeypot. Treat them as untrusted in Telegram messages (see the n8n README).
- **Rollback.** To disable the pipeline, remove the `<integration>` block and restart the Manager. Detection continues; only notifications stop.
