# M1.84 Architecture

M1.84 exposes root-confined filesystem and shell-free process operations as owned Future factories. File paths are relative to an injected root, traversal/absolute paths fail closed, and file reads use a bounded `max_bytes + 1` read rather than trusting only pre-read metadata.

Process execution accepts an executable plus argv and always invokes the host with `shell=False`; requesting a shell is rejected. stdin is bounded before spawn. stdout and stderr are pumped concurrently from `Popen` pipes into one shared byte budget while the process is running. Crossing the budget kills/reaps the child and returns `OUTPUT_LIMIT`; output is therefore not first captured without bounds and checked afterwards. Timeout also kills/reaps the child.

Argument count, input/output bytes, and timeout are immutable service limits. Returned process output is owned bytes with explicit exit status. No borrowed OS handles escape the service. This remains a hosted OS adapter rather than a claim of kernel-native completion APIs.
