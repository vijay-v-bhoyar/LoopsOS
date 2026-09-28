# Skill Fleet

`fleet.py` makes personal skill installation observable and fail-closed.

```powershell
$python = 'C:\Users\vijay\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -B skill-fleet/fleet.py build-registry --workspace . --output skill-fleet/registry.json
& $python -B skill-fleet/fleet.py validate --registry skill-fleet/registry.json
& $python -B skill-fleet/fleet.py sync --registry skill-fleet/registry.json --apply
```

Validation is read-only. Sync accepts only the canonical digest or a reviewed
baseline digest recorded in the registry; any other mirror is treated as an
unreviewed change. Provider, credential, and deployment tests are explicitly
outside this safe-local gate.
