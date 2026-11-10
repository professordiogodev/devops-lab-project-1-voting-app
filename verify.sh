#!/usr/bin/env bash
# Checks your repository and your running AWS infrastructure. Run with: ./verify.sh
cd "$(dirname "$0")" || exit 1
command -v aws >/dev/null || { echo "The AWS CLI is not installed." >&2; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { echo "No working AWS credentials (aws sts get-caller-identity fails)." >&2; exit 1; }
exec python3 .lab/p1check.py
