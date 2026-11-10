#!/usr/bin/env bash
# Proves nothing of Project 1 is left running in AWS. Run with: ./verify-teardown.sh
set -u
ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "No working AWS credentials." >&2; exit 1; }
echo "Checking account $ACCOUNT, region $(aws configure get region)"
pass=0; failn=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; failn=$((failn+1)); fi; }
empty() { local r; r=$(eval "$1" 2>/dev/null); [ -z "$r" ] || [ "$r" = None ]; }
T="Name=tag:Project,Values=cloudstack"
check "no running or stopped EC2 instance tagged Project=cloudstack" empty "aws ec2 describe-instances --filters $T Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text"
check "no NAT Gateway left (they bill every hour)" empty "aws ec2 describe-nat-gateways --filter $T Name=state,Values=pending,available,deleting --query 'NatGateways[].NatGatewayId' --output text"
check "no Elastic IP tagged Project=cloudstack" empty "aws ec2 describe-addresses --filters $T --query 'Addresses[].PublicIp' --output text"
check "no VPC tagged Project=cloudstack" empty "aws ec2 describe-vpcs --filters $T --query 'Vpcs[].VpcId' --output text"
check "no key pair named cloudstack" empty "aws ec2 describe-key-pairs --filters Name=key-name,Values=cloudstack --query 'KeyPairs[].KeyName' --output text"
check "no private key (*.pem) or .secrets/ folder left in this repository" bash -c "! ls *.pem .secrets >/dev/null 2>&1"
echo
if [ "$failn" -eq 0 ]; then echo "TEARDOWN VERIFIED ($pass/$pass) in account $ACCOUNT"; else echo "NOT CLEAN: $failn leftover(s). Remove them and run this again."; fi
exit "$failn"
