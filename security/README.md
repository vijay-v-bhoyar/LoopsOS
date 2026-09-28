# Security Evidence

## Authority Python 3.14.6 VEX

`authority-python-3.14.6.openvex.json` addresses three generic NVD CPE matches that Grype reports against the Python interpreter in the authority image:

- `CVE-2026-11940` maps to CPython issue `gh-151558`.
- `CVE-2026-11972` maps to CPython issue `gh-151981`.
- `CVE-2026-15308` maps to CPython issue `gh-153030`.

The official [Python 3.14.6 changelog](https://docs.python.org/3.14/whatsnew/changelog.html#python-3-14-6-final) lists all three fixes in that release. The VEX statements therefore use `fixed`, target only `pkg:generic/python@3.14.6`, and do not suppress any other package, version, or vulnerability. CI retains the resulting Grype JSON so reviewers can confirm the entries moved to `ignoredMatches` by VEX.
