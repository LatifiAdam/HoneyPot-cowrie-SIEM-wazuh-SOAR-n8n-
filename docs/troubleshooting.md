# Troubleshooting

Work through the pipeline in order. The first empty stage is where the problem is. See [`setup-guide.md`](setup-guide.md#step-6--end-to-end-test) for what "healthy" looks like at each stage.

```text
Cowrie → Agent → Manager rules → custom-n8n script → n8n → Telegram
```

## 1. Cowrie

| Symptom | Likely cause | Check / fix |
|---|---|---|
| `cowrie.json` missing or empty | Cowrie not running, or JSON log output disabled | Check Cowrie's status; make one SSH attempt on port `2222`; confirm the path in `cowrie-agent-localfile.xml` matches the real file. |
| Kali cannot connect to `2222` | Wrong IP, VM network mode, or firewall | `nmap -p 2222 <COWRIE_LAB_IP>` from Kali; confirm both VMs share a network. |

## 2. Wazuh Agent

| Symptom | Likely cause | Check / fix |
|---|---|---|
| Agent not **Active** | Not enrolled, or ports `1514`/`1515` blocked | `sudo /var/ossec/bin/agent_control -l` on the Manager; read `/var/ossec/logs/ossec.log` on the agent. |
| No "Analyzing file" line for the Cowrie log | `localfile` block outside `<ossec_config>`, wrong path, or agent not restarted | `sudo grep -i "analyzing file" /var/ossec/logs/ossec.log`; then `sudo systemctl restart wazuh-agent`. |
| Log-collector errors about the file | Path does not exist or is unreadable | `sudo test -r <path> && echo readable` |

## 3. Manager rules

| Symptom | Likely cause | Check / fix |
|---|---|---|
| Manager fails to start after editing rules | XML error or duplicate rule ID | `sudo /var/ossec/bin/wazuh-analysisd -t` prints the offending line. |
| Event arrives but no `1005xx` alert | Line is not a single JSON object, or the rule was not loaded | Paste the one-line event into `wazuh-logtest` (`jq -c . <file>` flattens it); confirm the manager was restarted. |
| `100501` fires but `100504` never does | Fewer than five failures from one source within 60 s, or `src_ip` not decoded | Send the same event repeatedly in one `wazuh-logtest` session. Failures spaced further apart than the 60 s timeframe do not correlate. |
| Several HIGH alerts in a row during one attack | The correlation rule can fire on each further failure inside the window | Expected. Tune with the rule `ignore` option or de-duplicate in n8n. |

## 4. `custom-n8n` integration

Start with `sudo tail -n 50 /var/ossec/logs/integrations.log` and `/var/ossec/logs/ossec.log`.

| Symptom | Likely cause | Check / fix |
|---|---|---|
| Script never runs | Name mismatch, wrong owner or mode, level above the alert level, or Manager not restarted | Confirm `ls -l /var/ossec/integrations/custom-n8n` shows `root wazuh` and `-rwxr-x---`; the file name must equal `<name>`; `<level>` must be at or below the alert level. |
| `Usage: custom-n8n.py <alert-json-path> <api-key> <webhook-url>` | Wazuh supplied a different number of arguments than the three the script accepts. This can happen if the Manager appends an extra argument, for example when integrator debug logging is on. | The script requires exactly three arguments. If you see this only in debug mode, change its check to accept a trailing optional argument. |
| `Missing token or invalid webhook URL` | Empty `<api_key>` or `<hook_url>` not starting with `http://` or `https://` | Fix the `<integration>` block. |
| `n8n HTTP error: 403` | Token mismatch between `<api_key>` and the n8n Header Auth credential | Re-enter the same secret in both places. |
| `n8n HTTP error: 404` | Workflow not published, or a `webhook-test` URL used outside test mode | Publish the workflow and use `/webhook/wazuh-cowrie-alert` in `<hook_url>`. |
| `Connection refused` or a timeout | n8n not running, wrong host or port, or `127.0.0.1` used while n8n is on another host or in a container without a published port | `curl -i http://127.0.0.1:5678/` from the Manager. The script's timeout is 15 s. |

Exit codes: `0` = webhook answered 2xx, `1` = HTTP or network error, `2` = usage or configuration error.

To see more detail, run the script by hand with a sample alert (see the setup guide). For integrator debug output, set `integrator.debug=2` in `/var/ossec/etc/local_internal_options.conf` and restart the Manager. Revert it afterwards, and note the usage-error row above.

## 5. n8n

| Symptom | Likely cause | Check / fix |
|---|---|---|
| No execution appears | Request never arrived, or it was rejected before the workflow | Run the curl test from the n8n README; compare the HTTP status with the table above. |
| Execution fails at **Edit Fields** | Expressions reference `$json.rule…` instead of `$json.body.rule…` | The Webhook node nests the POST body under `body`. |
| Everything goes to the LOW branch | `severity` is empty or a string, or the threshold is wrong | Inspect the IF node input in the execution view; use a **Number** comparison, `≥ 10`. |

## 6. Telegram

| Symptom | Likely cause | Check / fix |
|---|---|---|
| Execution succeeds, nothing arrives | Bot never started, wrong chat ID, or wrong bot token | Send `/start` to the bot from the receiving chat; re-check the credential and chat ID in the Telegram node. |
| Message fails to send, with a parse error | Parse mode set and the message contains characters that break it, such as attacker-supplied usernames | Use plain text (no parse mode) or escape the dynamic values. |
| Message fields run together on one line | No line breaks in the message template | Put each field on its own line in the Telegram node's text. |
