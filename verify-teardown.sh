#!/usr/bin/env bash
# Proves nothing of Project 1 is left running in AWS. Run with: ./verify-teardown.sh
set -u
# Use the region your Terraform uses (the default of variable "region" or a literal region = "...")
TFREGION=$(cat terraform/*.tf 2>/dev/null | tr '\n' ' ' | sed -n 's/.*variable *"region" *{[^}]*default *= *"\([a-z0-9-]*\)".*/\1/p')
[ -n "$TFREGION" ] || TFREGION=$(grep -h '^ *region *= *"' terraform/*.tf 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/')
[ -n "$TFREGION" ] && export AWS_DEFAULT_REGION="$TFREGION"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "No working AWS credentials." >&2; exit 1; }
echo "Checking account $ACCOUNT, region ${AWS_DEFAULT_REGION:-${AWS_REGION:-$(aws configure get region)}}"
pass=0; failn=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; failn=$((failn+1)); fi; }
empty() { local r; r=$(eval "$1" 2>/dev/null); [ -z "$r" ] || [ "$r" = None ]; }
STUDENT=$(bash "$(dirname "$0")/.lab/handle.sh") || exit 1
echo "Your handle: $STUDENT"
T="Name=tag:Project,Values=votingapp Name=tag:student,Values=$STUDENT"
check "no running or stopped EC2 instance tagged Project=votingapp and student=$STUDENT" empty "aws ec2 describe-instances --filters $T Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text"
check "no NAT Gateway left (they bill every hour)" empty "aws ec2 describe-nat-gateways --filter $T Name=state,Values=pending,available,deleting --query 'NatGateways[].NatGatewayId' --output text"
check "no Elastic IP tagged Project=votingapp" empty "aws ec2 describe-addresses --filters $T --query 'Addresses[].PublicIp' --output text"
check "no VPC tagged Project=votingapp" empty "aws ec2 describe-vpcs --filters $T --query 'Vpcs[].VpcId' --output text"
check "no Route 53 private zone of yours (Project=votingapp, student=$STUDENT) left" empty "aws resourcegroupstaggingapi get-resources --region us-east-1 --resource-type-filters route53:hostedzone --tag-filters Key=Project,Values=votingapp Key=student,Values=$STUDENT --query 'ResourceTagMappingList[].ResourceARN' --output text"
check "no DHCP options set tagged Project=votingapp" empty "aws ec2 describe-dhcp-options --filters $T --query 'DhcpOptions[].DhcpOptionsId' --output text"
check "no key pair named votingapp-$STUDENT" empty "aws ec2 describe-key-pairs --filters Name=key-name,Values=votingapp-$STUDENT --query 'KeyPairs[].KeyName' --output text"
check "no private key (*.pem) or .secrets/ folder left in this repository" bash -c "! compgen -G \"*.pem\" >/dev/null && [ ! -e .secrets ]"
echo
if [ "$failn" -eq 0 ]; then echo "TEARDOWN VERIFIED ($pass/$pass) in account $ACCOUNT"; else echo "NOT CLEAN: $failn leftover(s). Remove them and run this again."; fi
exit "$failn"
