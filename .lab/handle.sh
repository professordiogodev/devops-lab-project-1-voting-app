#!/usr/bin/env bash
# Prints your handle: your IAM user name in lowercase letters, digits and dashes (at most 14 characters).
# The labs put it in resource names and in the "student" tag, so classmates who share one AWS account never touch each other's resources.
# You never have to set it. To use another one, run:  export LAB_STUDENT=myhandle
slug() { printf '%s' "$1" | tr 'A-Z' 'a-z' | sed 's/[^a-z0-9][^a-z0-9]*/-/g; s/^-//; s/-$//' | cut -c1-14 | sed 's/-$//'; }
if [ -n "${LAB_STUDENT:-}" ]; then h=$(slug "$LAB_STUDENT"); else
  arn=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null) || { echo "No working AWS credentials (aws sts get-caller-identity fails)." >&2; exit 1; }
  n=${arn##*/}; n=${n%%@*}; h=$(slug "$n")
fi
[ -n "$h" ] || { echo "Could not make a handle from your IAM user name. Run: export LAB_STUDENT=myhandle" >&2; exit 1; }
if [ "${1:-}" = "--json" ]; then printf '{"student":"%s"}\n' "$h"; else printf '%s\n' "$h"; fi
