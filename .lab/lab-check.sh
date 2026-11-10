#!/usr/bin/env bash
rc=0
ls terraform/*.tf >/dev/null 2>&1 && echo "- ✅ terraform/ has .tf files" || { echo "- ❌ terraform/ has no .tf files"; rc=1; }
[ -x deploy.sh ] && grep -q 'set -euo pipefail' deploy.sh && echo "- ✅ deploy.sh is executable and strict" || { echo "- ❌ deploy.sh missing, not executable or without set -euo pipefail"; rc=1; }
[ -f systemd/clippy.service ] && echo "- ✅ systemd/clippy.service" || { echo "- ❌ systemd/clippy.service missing"; rc=1; }
ls nginx/* >/dev/null 2>&1 && echo "- ✅ nginx/ config" || { echo "- ❌ nginx/ config missing"; rc=1; }
if git ls-files | grep -qE '\.pem$|\.tfstate|(^|/)\.secrets/|\.env$'; then echo "- ❌ a key, state file or env file is committed"; rc=1; else echo "- ✅ no key, state or env file committed"; fi
grep -rEq 'AKIA[0-9A-Z]{16}' . --exclude-dir=.git --exclude-dir=.terraform --exclude=p1check.py && { echo "- ❌ an AWS access key is committed"; rc=1; } || echo "- ✅ no AWS access key committed"
grep -qE '^ALL CHECKS PASSED \(' SUBMISSION.md && echo "- ✅ SUBMISSION.md shows ALL CHECKS PASSED" || { echo "- ❌ paste the verify.sh output ('ALL CHECKS PASSED') into SUBMISSION.md"; rc=1; }
exit $rc
