# MITRE ATT&CK mapping

This document maps behaviours simulated in the lab to ATT&CK. The mapping gives analysts a vocabulary for describing observed activity; it does not imply that Wazuh automatically detects every technique listed here.

| Lab activity | Technique | Why it fits | Lab evidence | Dedicated Wazuh rule |
|---|---|---|---|---|
| Nmap scan of the honeypot's SSH port | [T1046 — Network Service Discovery](https://attack.mitre.org/techniques/T1046/) | The test identifies an exposed network service and its port. | Kali Nmap output and connection telemetry | No |
| Repeated SSH password guesses | [T1110.001 — Password Guessing](https://attack.mitre.org/techniques/T1110/001/) | Authentication attempts use guessed passwords. | Cowrie `cowrie.login.failed` | Yes: `100501`, `100504` |
| SSH connection/session to the emulated host | [T1021.004 — SSH](https://attack.mitre.org/techniques/T1021/004/) | The remote access protocol used by the test is SSH. | Cowrie session and authentication records | Partly: `100502` (successful login) |
| Shell commands entered after login | [T1059.004 — Unix Shell](https://attack.mitre.org/techniques/T1059/004/) | Commands entered into the emulated Unix shell represent shell-interpreter activity. | Cowrie `cowrie.command.input` | Yes: `100503` |

## Detection coverage notes

- `100501` detects each Cowrie failed-login event.
- `100504` raises a higher-severity alert when five failures from the same source are correlated within 60 seconds.
- `100502` and `100503` cover successful login and command-input event types respectively.
- The Nmap scan is documented as a simulated discovery behaviour. Unless a dedicated scan-detection rule or network sensor is configured, do not claim that this scan itself generated a specific Wazuh detection.

Technique mappings should be reviewed whenever the test scenarios or custom rules change.

## Optional: tag the rules with ATT&CK IDs

The custom rules do not currently carry ATT&CK metadata, so Wazuh's MITRE views will not attribute these alerts to a technique. To change that, add a `<mitre>` element inside each relevant rule in `config/local_rules.xml`, for example in rule `100501` and `100504`:

```xml
<mitre>
  <id>T1110.001</id>
</mitre>
```

Validate with `wazuh-analysisd -t` and `wazuh-logtest` before restarting the Manager.
