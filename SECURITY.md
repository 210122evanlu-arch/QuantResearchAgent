# Security Policy

This repository is a research prototype, not a trading, compliance, or investment-advice system. Do not submit confidential research, client data, brokerage credentials, API keys, or licensed market data in issues or pull requests.

If a credential is exposed, revoke or rotate it immediately and remove it from the complete Git history. Report suspected vulnerabilities privately to the repository owner rather than through a public issue.

The CI pipeline scans release candidates for common secret patterns and audits locked runtime dependencies. These checks reduce risk but do not replace human review or an enterprise secret-scanning service.
