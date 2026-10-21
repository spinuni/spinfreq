# Native Windows runtime evidence ledger

Candidate `0.1.0rc2` implements native Windows computation as an explicit
`--mode compute` opt-in. Default Windows mode remains preview. Linux/WSL2 is the
locally exercised compute platform; the numerical operators are unchanged.

| Evidence | Local status | Native Windows gate |
| --- | --- | --- |
| Win32 structure integer widths/64-bit ABI | Checked on Linux | Included in native CI |
| Memory limit refuses a 512 MiB request with a 128 MiB test cap | Skipped: native-only | Must pass |
| One-second user-CPU job limit terminates a busy worker | Skipped: native-only | Must pass |
| Failed job assignment never opens startup gate | Skipped: native-only | Must pass |
| Cancellation and normal completion remove child process tree | Skipped: native-only | Must pass |
| Queue, isolation, owner lease, timeout/disk, server crash/restart and numerical jobs | Linux regression exercised | Must pass with Windows backend |
| Browser through numerical worker to downloaded artifacts | Linux exercised | Native Chromium CI configured; must pass before qualification |

The CI platform matrix runs Windows tests on an actual Windows host. Its outcomes
cannot currently be retrieved through the GitHub API from this workspace. No
native passes, Windows resource measurements or Windows performance claims are
inferred from Linux tests or portable ABI inspection. The Windows gate is open.

See [implementation and commands](../../../docs/development/WINDOWS.md) for the
exact memory/CPU/disk contract and [workflow](../../../.github/workflows/ci.yml)
for automation. Do not enable native Windows computation automatically until the
native lifecycle/resource and end-to-end evidence has passed review.

The CI upload named `native-windows-qualification` includes the real Chromium
report, screenshots, downloaded result archive and server logs. The report saves
`server_platform` and `worker_runtime`, so Linux execution cannot be mistaken for
native Windows Job Object evidence. `status.json` records what has actually been
observed locally; it is not an assertion that hosted CI passed.
