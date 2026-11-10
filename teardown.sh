#!/usr/bin/env bash
# Destroys what your Terraform created. Run with: ./teardown.sh
set -u
cd "$(dirname "$0")/terraform" 2>/dev/null || { echo "No terraform/ directory." >&2; exit 1; }
terraform destroy -auto-approve
echo "Now delete your state bucket (empty it first, including all versions), cloudstack.pem and .secrets/, then run ./verify-teardown.sh"
