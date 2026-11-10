#!/usr/bin/env python3
"""Project 1 checker: your repository, your real AWS account (resources tagged Project=votingapp) and the live app."""
import glob, json, os, re, socket, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
passed = failed = 0


def check(desc, ok, hint=""):
    global passed, failed
    if ok:
        passed += 1
        print("PASS  " + desc)
    else:
        failed += 1
        print("FAIL  " + desc + (("   -> " + hint) if hint else ""))


def aws(*args):
    try:
        out = subprocess.check_output(("aws",) + args + ("--output", "json"), stderr=subprocess.DEVNULL, timeout=60)
        return json.loads(out or "null")
    except Exception:
        return None


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def read(p):
    try:
        return open(p).read()
    except OSError:
        return ""


print("== Your repository ==")
tf = sorted(glob.glob("terraform/*.tf"))
alltf = "\n".join(read(f) for f in tf)
check("terraform/ has .tf files", bool(tf), "put all your Terraform in terraform/")
check("terraform fmt -check is clean", subprocess.run("terraform -chdir=terraform fmt -check -recursive", shell=True, capture_output=True).returncode == 0 and bool(tf), "terraform -chdir=terraform fmt")
check("remote state: S3 backend with use_lockfile = true",
      bool(re.search(r'backend\s+"s3"', alltf)) and bool(re.search(r"use_lockfile\s*=\s*true", alltf)), "see the brief")
m = re.search(r'bucket\s*=\s*"([^"]+)"', alltf)
if m:
    v = aws("s3api", "get-bucket-versioning", "--bucket", m.group(1))
    check("the state bucket %s has versioning enabled" % m.group(1), bool(v) and v.get("Status") == "Enabled")
else:
    check("the state bucket has versioning enabled", False, "no bucket = \"...\" in your backend block")
gi = read(".gitignore")
check(".gitignore excludes *.pem, *.tfstate* and env files", "*.pem" in gi and "*.tfstate" in gi and (".env" in gi))
bad = [f for f in sh("git ls-files").split("\n") if re.search(r"\.pem$|\.tfstate|\.env$|(^|/)\.secrets/", f)]
check("no key, state file or env file is committed", not bad, "committed: " + ", ".join(bad))
check("no AWS access key in the repository", not sh("git grep -lE 'AKIA[0-9A-Z]{16}' -- . ':!.lab' ':!verify.sh' 2>/dev/null").strip())
units = glob.glob("systemd/*.service")
good = [u for u in units if re.search(r"^Restart=on-failure", read(u), re.M) and re.search(r"^User=(?!root)\S+", read(u), re.M) and re.search(r"^ExecStart=", read(u), re.M)]
check("systemd/ has at least 3 unit files, each with a non-root User= and Restart=on-failure", len(units) >= 3 and len(good) == len(units), "%d units, %d good" % (len(units), len(good)))
deploy = read("deploy.sh")
check("deploy.sh exists, is executable and uses set -euo pipefail", os.access("deploy.sh", os.X_OK) and "set -euo pipefail" in deploy)
check("deploy.sh takes addresses from terraform output (no hardcoded server IPs)",
      "terraform" in deploy and "output" in deploy and not re.search(r"\b10\.0\.\d{1,3}\.\d{1,3}\b(?!/)", deploy))
check("README.md explains how to provision, deploy and SSH to the private servers", len(read("README.md")) > 400 and "ssh" in read("README.md").lower())
check("an architecture diagram is in docs/ or the README",
      bool(glob.glob("docs/*.png") + glob.glob("docs/*.svg") + glob.glob("docs/*.jpg")) or "```mermaid" in read("README.md") or bool(re.search(r"!\[.*\]\(.*\)", read("README.md"))))

print("== Your AWS account (resources tagged Project=votingapp) ==")
F = "Name=tag:Project,Values=votingapp"
vpcs = (aws("ec2", "describe-vpcs", "--filters", F) or {}).get("Vpcs", [])
check("a VPC tagged Project=votingapp exists", bool(vpcs), "provider block: default_tags { tags = { Project = \"votingapp\" } }")
if not vpcs:
    print("\nNothing else can be checked without the VPC.\n%d check(s) failed, %d passed" % (failed, passed))
    sys.exit(1)
vid = vpcs[0]["VpcId"]
VF = "Name=vpc-id,Values=" + vid
subnets = (aws("ec2", "describe-subnets", "--filters", VF) or {}).get("Subnets", [])
rts = (aws("ec2", "describe-route-tables", "--filters", VF) or {}).get("RouteTables", [])
nats = (aws("ec2", "describe-nat-gateways", "--filter", VF, "Name=state,Values=available,pending") or {}).get("NatGateways", [])


def default_target(sid):
    chosen = None
    for rt in rts:
        if any(a.get("SubnetId") == sid for a in rt["Associations"]):
            chosen = rt
    if chosen is None:
        chosen = next((rt for rt in rts if any(a.get("Main") for a in rt["Associations"])), None)
    for r in (chosen or {}).get("Routes", []):
        if r.get("DestinationCidrBlock") == "0.0.0.0/0":
            if r.get("GatewayId", "").startswith("igw-"):
                return "igw"
            if r.get("NatGatewayId"):
                return "nat"
    return None


kind = {s["SubnetId"]: default_target(s["SubnetId"]) for s in subnets}
check("at least one public subnet (route to an Internet Gateway) and one private subnet (route to a NAT Gateway)",
      "igw" in kind.values() and "nat" in kind.values(), "routes found: %s" % list(kind.values()))
check("a NAT Gateway is available and sits in a public subnet", len(nats) == 1 and kind.get(nats[0]["SubnetId"]) == "igw")

insts = []
for r in (aws("ec2", "describe-instances", "--filters", F, "Name=instance-state-name,Values=running,pending") or {}).get("Reservations", []):
    insts += r["Instances"]
by = {next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), ""): i for i in insts}
NAMES = ["vote-server", "result-server", "worker-server", "redis-server", "db-server"]
check("five running servers named " + ", ".join(NAMES), sorted(by) == sorted(NAMES), "found: %s" % sorted(by))
vote, result, worker, redis, db = (by.get(n, {}) for n in NAMES)
check("vote-server and result-server are in a public subnet and have a public IP",
      all(x.get("PublicIpAddress") and kind.get(x.get("SubnetId")) == "igw" for x in (vote, result)) and bool(vote) and bool(result))
check("worker, redis and db servers are in private subnets and have NO public IP",
      all(x and not x.get("PublicIpAddress") and kind.get(x.get("SubnetId")) == "nat" for x in (worker, redis, db)))
check("IMDSv2 is required on all servers", len(insts) > 0 and all(i["MetadataOptions"]["HttpTokens"] == "required" for i in insts))
check("all servers use the same key pair", len({i.get("KeyName") for i in insts}) == 1 and bool(insts))


def sg_ids(i):
    return [g["GroupId"] for g in i.get("SecurityGroups", [])]


def ingress(i):
    ids = sg_ids(i)
    if not ids:
        return []
    rs = (aws("ec2", "describe-security-group-rules", "--filters", "Name=group-id,Values=" + ",".join(ids)) or {}).get("SecurityGroupRules", [])
    return [r for r in rs if not r["IsEgress"]]


def srcs(rules, port):
    return {r.get("ReferencedGroupInfo", {}).get("GroupId") or r.get("CidrIpv4") for r in rules if r["FromPort"] <= port <= r["ToPort"]}


print("== Security groups: each service trusts only the machines that call it ==")
ri = {n: ingress(by[n]) for n in by}
for n in ("vote-server", "result-server"):
    r = ri.get(n, [])
    check("%s: port 80 open to the world, port 22 only from ONE address (or a security group), nothing else" % n,
          "0.0.0.0/0" in srcs(r, 80) and "0.0.0.0/0" not in srcs(r, 22) and all(x["FromPort"] in (22, 80) and x["ToPort"] in (22, 80) for x in r) and bool(srcs(r, 22)))
sv, sr, sw = (sg_ids(x) for x in (vote, result, worker))
check("redis-server: port 6379 only from the vote and worker security groups (not a CIDR)",
      srcs(ri.get("redis-server", []), 6379) == set(sv) | set(sw) and bool(sv) and bool(sw),
      "found %s; use referenced_security_group_id" % sorted(srcs(ri.get("redis-server", []), 6379), key=str))
check("db-server: port 5432 only from the worker and result security groups (not a CIDR)",
      srcs(ri.get("db-server", []), 5432) == set(sw) | set(sr) and bool(sw) and bool(sr),
      "found %s" % sorted(srcs(ri.get("db-server", []), 5432), key=str))
check("worker-server accepts nothing except SSH (the worker only calls out)",
      all(x["FromPort"] == 22 and x["ToPort"] == 22 for x in ri.get("worker-server", [])))
check("no private server accepts SSH from a CIDR (only through the jump host's security group)",
      all(not x.get("CidrIpv4") for n in ("worker-server", "redis-server", "db-server") for x in ri.get(n, [])))

print("== Live: the real app ==")


def http(url, data=None, headers=None, t=10):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=t) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def scores(base):
    try:
        h = http(base + "/socket.io/?EIO=4&transport=polling")[1]
        sid = json.loads(h[h.index("{"):])["sid"]
        u = base + "/socket.io/?EIO=4&transport=polling&sid=" + sid
        http(u, b"40")
        end = time.time() + 12
        while time.time() < end:
            for pkt in http(u, t=14)[1].split("\x1e"):
                m = re.match(r'42\["scores","(.*)"\]$', pkt)
                if m:
                    return json.loads(m.group(1).encode().decode("unicode_escape"))
    except Exception:
        pass
    return None


vip, rip = vote.get("PublicIpAddress"), result.get("PublicIpAddress")
if vip and rip:
    st, body = http("http://%s/" % vip)
    check("the vote page answers 200 on port 80 and shows the two options", st == 200 and "vote" in body.lower())
    st, body = http("http://%s/" % rip)
    check("the result page answers 200 on port 80", st == 200)
    before = scores("http://%s" % rip)
    check("the result server can read PostgreSQL (the page receives live scores)", before is not None, "result -> db :5432 and the host name 'db'")
    voter = "check%d" % int(time.time())
    st, _ = http("http://%s/" % vip, b"vote=a", {"Cookie": "voter_id=" + voter, "Content-Type": "application/x-www-form-urlencoded"})
    check("a vote can be cast through the public vote page (vote -> redis works)", st == 200, "vote -> redis :6379 and the host name 'redis'")
    after = None
    for _ in range(8):
        time.sleep(3)
        after = scores("http://%s" % rip)
        if before and after and after.get("a", 0) > before.get("a", 0):
            break
    check("the vote arrives on the result page within 25 seconds (worker moved it from redis to postgres)",
          bool(before) and bool(after) and after.get("a", 0) > before.get("a", 0), "look at: journalctl -u worker on the worker server")
    for name, host, port in (("redis-server", redis, 6379), ("db-server", db, 5432), ("worker-server", worker, 22)):
        ip = host.get("PrivateIpAddress", "")
        s = socket.socket(); s.settimeout(4)
        try:
            s.connect((ip, port)); closed = False
        except OSError:
            closed = True
        finally:
            s.close()
        check("%s %s:%d times out from your laptop (private)" % (name, ip, port), closed)
    for port in (6379, 5432):
        s = socket.socket(); s.settimeout(4)
        try:
            s.connect((vip, port)); closed = False
        except OSError:
            closed = True
        finally:
            s.close()
        check("port %d on the public vote-server IP is closed" % port, closed)
else:
    check("the web servers have public IPs to test", False)

print()
if failed == 0:
    print("ALL CHECKS PASSED (%d/%d)" % (passed, passed))
else:
    print("%d check(s) failed, %d passed" % (failed, passed))
sys.exit(1 if failed else 0)
