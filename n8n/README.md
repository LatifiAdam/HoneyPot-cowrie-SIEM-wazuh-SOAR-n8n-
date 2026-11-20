# n8n workflow

The implemented workflow (named *Wazuh - cowrie SOAR* in the screenshots) is:

```text
Webhook (POST) → Edit Fields → IF (severity ≥ 10) ─ true  → Telegram HIGH
                                                   └ false → Telegram LOW
```

See [`05-n8n-high-low-workflow.png`](../screenshots/05-n8n-high-low-workflow.png) for the layout and [`06-n8n-successful-execution.png`](../screenshots/06-n8n-successful-execution.png) for a completed run.

| Node | Purpose |
|---|---|
| **Webhook** | Receives the Wazuh alert JSON from the `custom-n8n` integration and checks the shared token. |
| **Edit Fields** | Flattens the nested Wazuh alert into the few fields the messages need. |
| **IF** | Routes by severity: `true` for level 10 and above, `false` otherwise. |
| **Telegram** (two nodes) | Send the HIGH or LOW message. The screenshot shows n8n's default names (*Send a text message* and *Send a text message1*); renaming them *Telegram HIGH* and *Telegram LOW* makes executions easier to read. |

## 1. Webhook node

| Setting | Value |
|---|---|
| HTTP Method | `POST` |
| Path | `wazuh-cowrie-alert` |
| Authentication | Header Auth |
| Header name | `X-Wazuh-Token` |
| Header value | A newly generated secret, identical to `<api_key>` in the Wazuh Manager integration |
| Respond | Either mode works. *Immediately* stops Telegram latency from using up the integration script's 15-second timeout. |

n8n shows two URLs for the node:

| URL | When it works |
|---|---|
| `http://<N8N_HOST>:5678/webhook-test/wazuh-cowrie-alert` | Only while the editor is listening for a test event. |
| `http://<N8N_HOST>:5678/webhook/wazuh-cowrie-alert` | Only after the workflow is **published** (called *Activate* in older n8n versions). Use this one in the Wazuh `<hook_url>`. |

The integration runs on the Wazuh Manager, so `127.0.0.1` is correct only if n8n runs on that same host and port `5678` is reachable from it.

The Webhook node nests the request under `body`, so the Wazuh alert is at `$json.body`. In later nodes, write `{{ $json.body.rule.level }}`, not `{{ $json.rule.level }}`.

## 2. Edit Fields node

Create these fields. The names follow the Telegram messages in screenshots 07 and 08. The expressions are suggested mappings onto the standard Wazuh alert layout (see [`samples/wazuh-alert-100504.example.json`](../samples/wazuh-alert-100504.example.json)), so check them against your own node.

| Field | Type | Suggested expression | Telegram label |
|---|---|---|---|
| `severity` | Number | `{{ $json.body.rule.level }}` | Severity |
| `rule_id` | String | `{{ $json.body.rule.id }}` | Rule ID |
| `detection` | String | `{{ $json.body.rule.description }}` | Detection |
| `src_ip` | String | `{{ $json.body.data.src_ip }}` | Source IP |
| `username` | String | `{{ $json.body.data.username }}` | Username |
| `event` | String | `{{ $json.body.data.eventid }}` | Event |
| `command` | String | `{{ $json.body.data.input ?? 'N/A' }}` | Command (`N/A` unless the event is `cowrie.command.input`) |
| `honeypot` | String | `{{ $json.body.data.sensor }}` or `{{ $json.body.agent.name }}` | Honeypot |
| `time` | String | `{{ $json.body.timestamp }}` | Time |

`severity` must be a **Number**, otherwise the IF comparison below can misroute alerts.

## 3. IF node

| Setting | Value |
|---|---|
| Value 1 | `{{ $json.severity }}` |
| Operation | Number → is greater than or equal to |
| Value 2 | `10` |

With the lab rules this routes `100502` (level 10) and `100504` (level 12) to HIGH, and `100501` (level 7) and `100503` (level 8) to LOW. Wazuh levels run from 0 to 15, which is why the messages read `Severity: 12/15`. Keep this threshold in line with the `<level>` in the Manager integration and with your own severity policy.

## 4. Telegram nodes

Create a Telegram credential with the bot token from BotFather. Send `/start` to the bot from the receiving chat before the first test. Set the **Chat ID** in each node. Neither value belongs in Git.

Message templates matching the captured output:

**HIGH** (`true` branch):

```text
🚨 HIGH SEVERITY — COWRIE ALERT
Severity: {{ $json.severity }}/15
Rule ID: {{ $json.rule_id }}
Detection: {{ $json.detection }}
Source IP: {{ $json.src_ip }}
Username: {{ $json.username }}
Event: {{ $json.event }}
Command: {{ $json.command }}
Honeypot: {{ $json.honeypot }}
Time: {{ $json.time }}
ACTION: Investigate this activity immediately.
```

**LOW** (`false` branch):

```text
🟡 LOW SEVERITY — COWRIE ALERT
Severity: {{ $json.severity }}/15
Rule ID: {{ $json.rule_id }}
Detection: {{ $json.detection }}
Source IP: {{ $json.src_ip }}
Username: {{ $json.username }}
Event: {{ $json.event }}
Honeypot: {{ $json.honeypot }}
Time: {{ $json.time }}
STATUS: Logged for monitoring.
```

Notes:

- **One field per line.** In the captured screenshots the fields run together in one paragraph. Explicit line breaks, as above, make alerts much easier to scan.
- **Untrusted text.** `username`, `command` and `src_ip` originate from whoever attacks the honeypot. Leave **Parse Mode** unset (plain text), or escape these values if you use HTML or Markdown, so crafted input cannot break or spoof the message.
- **Footer.** The italic *This message was sent automatically with n8n* line is n8n's attribution option on the Telegram node. It can be switched off.

## 5. Testing

Test the webhook on its own, without Wazuh. Click **Execute workflow** in the editor so the test URL is listening, then:

```bash
export WAZUH_TOKEN='<the shared secret>'
curl -sS -i -X POST "http://127.0.0.1:5678/webhook-test/wazuh-cowrie-alert" \
  -H "Content-Type: application/json" \
  -H "X-Wazuh-Token: $WAZUH_TOKEN" \
  --data @samples/wazuh-alert-100504.example.json
```

| Result | Meaning |
|---|---|
| `200`, execution on the **true** branch, HIGH message in Telegram | Working. The sample alert is level 12. |
| `403` | Header name or secret does not match the Header Auth credential. |
| `404` | The test URL is not listening, or the workflow is not published (for the production URL). |
| `200` but no Telegram message | Check the Telegram node's error in the execution view; see [`docs/troubleshooting.md`](../docs/troubleshooting.md#6-telegram). |

To exercise the LOW branch, copy the sample and set `rule.level` to `7`. Repeat the test against the production URL after publishing, then clear the shell history entry that contains the token.

## Sanitized workflow export

An export can be added here as `workflow.sanitized.json` after removing or replacing credential references, Telegram chat IDs, webhook identifiers, internal addresses, hostnames, and all token and secret values. Re-import the sanitized export into a disposable n8n instance to verify that its node structure remains valid.

Never commit the n8n database, `.n8n/` directory, credential store, encryption key, or live execution payloads.
