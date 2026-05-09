# Security policy

## Supported versions

This project is small and currently single-track. Only the `main` branch
is supported. Pin to a specific commit or tag if you need stability.

## Reporting a vulnerability

If you find a security issue — for example, a path-traversal escape from
the `--results-dir` validation, a generated script that ignores its
timeout, or a way to make the renderer fabricate a passing row — please
**do not** open a public issue.

Instead, open a private security advisory on GitHub:

1. Go to https://github.com/hzang12345-ship-it/hermes-swarm-benchmark/security/advisories
2. Click **Report a vulnerability**.
3. Include reproduction steps, the commit hash, your platform, and an
   assessment of impact.

You should expect an acknowledgement within a few business days. If the
issue is confirmed, a fix will land on `main` and a CHANGELOG entry will
describe it after public disclosure.

## Threat model — what's in scope

- Anything that lets a malicious `--results-dir`, manifest, or per-agent
  JSON cause the renderer to produce misleading output (false PASS, false
  totals, hidden failures).
- Anything that lets a generated sub-agent script execute outside its
  60-second timeout, or write outside its declared `{test}/{agent}.json`
  path.
- Anything that lets `hermes-benchmark` write outside the user-specified
  `--results-dir` / `--goal-out` paths.

## Out of scope

- Issues in the Hermes harness itself — please report those upstream.
- Issues that require an attacker who already has write access to your
  results directory; this package treats the local filesystem as
  trusted.
- Performance / DoS in the absence of an exploitable correctness bug.

Thanks for helping keep the project honest.
