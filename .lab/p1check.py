#!/usr/bin/env python3
"""Project 1 checker: reads your repository and your real AWS account (resources tagged Project=cloudstack)."""
import glob, json, os, re, subprocess, sys, urllib.request

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


def tracked():
    return sh("git ls-files").split("\n")


# ---------------------------------------------------------------- repository
print("== Your repository ==")
tf = sorted(glob.glob("terraform/*.tf"))
alltf = "\n".join(read(f) for f in tf)
check("terraform/ has .tf files", bool(tf), "put all your Terraform in terraform/")
fmt = subprocess.run("terraform -chdir=terraform fmt -check -recursive", shell=True, capture_output=True)
check("terraform fmt -check is clean", fmt.returncode == 0 and bool(tf), "run: terraform -chdir=terraform fmt")
check("remote state: S3 backend with use_lockfile = true",
      re.search(r'backend\s+"s3"', alltf) and re.search(r"use_lockfile\s*=\s*true", alltf), "see the brief: S3 native locking")
m = re.search(r'bucket\s*=\s*"([^"]+)"', alltf)
if m:
    v = aws("s3api", "get-bucket-versioning", "--bucket", m.group(1))
    check("the state bucket %s has versioning enabled" % m.group(1), bool(v) and v.get("Status") == "Enabled",
          "aws s3api put-bucket-versioning ...")
else:
    check("the state bucket has versioning enabled", False, "no bucket = \"...\" found in your backend block")
gi = read(".gitignore")
check(".gitignore excludes *.pem, *.tfstate* and env files",
      "*.pem" in gi and ("*.tfstate" in gi) and (".env" in gi or "*.env" in gi))
bad = [f for f in tracked() if re.search(r"\.pem$|\.tfstate|(^|/)\.env$|\.env$|(^|/)\.secrets/", f)]
check("no key, state file or env file is committed", not bad, "committed: " + ", ".join(bad))
check("no AWS access key in the repository",
      not sh("git grep -lE 'AKIA[0-9A-Z]{16}' -- . ':!.lab' ':!verify.sh' 2>/dev/null").strip())
unit = read("systemd/clippy.service")
check("systemd/clippy.service: User=clippy, Restart=on-failure and an EnvironmentFile",
      re.search(r"^User=clippy", unit, re.M) and re.search(r"^Restart=on-failure", unit, re.M) and re.search(r"^EnvironmentFile=", unit, re.M))
deploy = read("deploy.sh")
check("deploy.sh exists, is executable and uses set -euo pipefail", os.access("deploy.sh", os.X_OK) and "set -euo pipefail" in deploy)
check("deploy.sh reads IPs from terraform output (no hardcoded private IPs)",
      "terraform" in deploy and "output" in deploy and not re.search(r"\b10\.0\.[23]\.\d{1,3}\b(?!/)", deploy))
check("nginx/ has a config that proxy_passes to the app", any("proxy_pass" in read(f) for f in glob.glob("nginx/*")))
check("README.md explains how to provision, deploy and SSH to the private servers", len(read("README.md")) > 400 and "ssh" in read("README.md").lower())
check("an architecture diagram is in docs/ or the README",
      bool(glob.glob("docs/*.png") + glob.glob("docs/*.svg") + glob.glob("docs/*.jpg")) or "```mermaid" in read("README.md") or bool(re.search(r"!\[.*\]\(.*\)", read("README.md"))))

# ---------------------------------------------------------------- AWS
print("== Your AWS account (resources tagged Project=cloudstack) ==")
F = "Name=tag:Project,Values=cloudstack"
vpcs = (aws("ec2", "describe-vpcs", "--filters", F) or {}).get("Vpcs", [])
vpc = vpcs[0] if vpcs else None
check("a VPC tagged Project=cloudstack exists with CIDR 10.0.0.0/16", bool(vpc) and vpc["CidrBlock"] == "10.0.0.0/16",
      "tag everything with default_tags { Project = \"cloudstack\" } in the provider block")
if not vpc:
    print("\nNothing else can be checked without the VPC.")
    print("%d check(s) failed, %d passed" % (failed, passed))
    sys.exit(1)
vid = vpc["VpcId"]
VF = "Name=vpc-id,Values=" + vid
subnets = (aws("ec2", "describe-subnets", "--filters", VF) or {}).get("Subnets", [])
rts = (aws("ec2", "describe-route-tables", "--filters", VF) or {}).get("RouteTables", [])
igws = (aws("ec2", "describe-internet-gateways", "--filters", "Name=attachment.vpc-id,Values=" + vid) or {}).get("InternetGateways", [])
nats = (aws("ec2", "describe-nat-gateways", "--filter", VF, "Name=state,Values=available,pending") or {}).get("NatGateways", [])


def default_target(subnet_id):
    """Where does 0.0.0.0/0 go for this subnet? 'igw', 'nat' or None."""
    chosen = None
    for rt in rts:
        if any(a.get("SubnetId") == subnet_id for a in rt["Associations"]):
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


kinds = [default_target(s["SubnetId"]) for s in subnets]
check("an Internet Gateway is attached", len(igws) == 1)
check("1 public subnet (route to the IGW) and 2 private subnets (route to the NAT Gateway)",
      kinds.count("igw") == 1 and kinds.count("nat") == 2, "found routes: %s" % kinds)
check("a NAT Gateway is available and sits in the public subnet",
      len(nats) == 1 and default_target(nats[0]["SubnetId"]) == "igw")

insts = []
for r in (aws("ec2", "describe-instances", "--filters", F, "Name=instance-state-name,Values=running,pending") or {}).get("Reservations", []):
    insts += r["Instances"]
by = {}
for i in insts:
    n = next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "")
    by[n] = i
check("three running instances named proxy-server, app-server, data-server", set(by) == {"proxy-server", "app-server", "data-server"},
      "found: %s" % sorted(by))
px, ap, da = by.get("proxy-server", {}), by.get("app-server", {}), by.get("data-server", {})
check("instance types: proxy t3.micro, app t3.small, data t3.small",
      (px.get("InstanceType"), ap.get("InstanceType"), da.get("InstanceType")) == ("t3.micro", "t3.small", "t3.small"))
eip = (aws("ec2", "describe-addresses", "--filters", "Name=instance-id,Values=" + px.get("InstanceId", "none")) or {}).get("Addresses", [])
check("the proxy has an Elastic IP", len(eip) == 1)
check("the app and data servers have NO public IP", bool(ap) and bool(da) and not ap.get("PublicIpAddress") and not da.get("PublicIpAddress"))
check("IMDSv2 is required on all three instances",
      len(insts) == 3 and all(i["MetadataOptions"]["HttpTokens"] == "required" for i in insts))
check("all three use the same key pair", len({i.get("KeyName") for i in insts}) == 1 and bool(insts))
check("the app server is in a private subnet and the data server in a different private subnet",
      bool(ap) and bool(da) and ap["SubnetId"] != da["SubnetId"] and default_target(ap["SubnetId"]) == "nat" and default_target(da["SubnetId"]) == "nat")


def rules_of(inst):
    ids = [g["GroupId"] for g in inst.get("SecurityGroups", [])]
    if not ids:
        return [], ids
    rs = (aws("ec2", "describe-security-group-rules", "--filters", "Name=group-id,Values=" + ",".join(ids)) or {}).get("SecurityGroupRules", [])
    return [r for r in rs if not r["IsEgress"]], ids


prx, pids = rules_of(px)
apr, aids = rules_of(ap)
dar, dids = rules_of(da)


def ports(rs):
    return sorted((r["FromPort"], r["ToPort"]) for r in rs)


print("== Security groups: each tier trusts only the one in front of it ==")
check("sg-proxy: port 80 from anywhere, port 22 from ONE address only (not 0.0.0.0/0)",
      any(r["FromPort"] == 80 and r.get("CidrIpv4") == "0.0.0.0/0" for r in prx)
      and any(r["FromPort"] == 22 and r.get("CidrIpv4", "").endswith("/32") for r in prx)
      and not any(r["FromPort"] <= 22 <= r["ToPort"] and r.get("CidrIpv4") == "0.0.0.0/0" for r in prx),
      "port 22 must be your own /32")
check("sg-proxy opens nothing else to the world",
      all(r["FromPort"] in (22, 80) for r in prx))
check("sg-app: only 8000 and 22, and both come from the proxy's security group (not a CIDR)",
      ports(apr) == [(22, 22), (8000, 8000)] and all(r.get("ReferencedGroupInfo", {}).get("GroupId") in pids for r in apr),
      "use referenced_security_group_id")
check("sg-data: only 5432, 6379 and 22; the database ports come from the app's security group, ssh from the proxy's",
      ports(dar) == [(22, 22), (5432, 5432), (6379, 6379)]
      and all(r.get("ReferencedGroupInfo", {}).get("GroupId") in aids for r in dar if r["FromPort"] != 22)
      and all(r.get("ReferencedGroupInfo", {}).get("GroupId") in pids for r in dar if r["FromPort"] == 22))

# ---------------------------------------------------------------- live
print("== Live: the public URL and the walls ==")
ip = px.get("PublicIpAddress")
if ip:
    def http(method, url, data=None, t=10):
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=t) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception:
            return 0, ""
    st, _ = http("GET", "http://%s/healthz" % ip)
    check("GET http://<elastic-ip>/healthz -> 200", st == 200)
    st, body = http("POST", "http://%s/shorten" % ip, b'{"url":"https://ironhack.com"}')
    code = ""
    try:
        code = json.loads(body)["short_code"]
    except Exception:
        pass
    check("POST /shorten returns a short code (the app reaches PostgreSQL)", st in (200, 201) and bool(code))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        op = urllib.request.build_opener(NoRedirect)
        r = op.open("http://%s/r/%s" % (ip, code), timeout=10)
        st = r.status
    except urllib.error.HTTPError as e:
        st = e.code
    except Exception:
        st = 0
    check("GET /r/<code> redirects (302)", code and st == 302)
    st, body = http("GET", "http://%s/stats" % ip)
    check("/stats reports store=postgres and cache=redis (both data services are used)", '"postgres"' in body and '"redis"' in body)
    for port in (8000, 5432, 6379):
        import socket
        sk = socket.socket(); sk.settimeout(4)
        try:
            sk.connect((ip, port)); closed = False
        except OSError:
            closed = True
        finally:
            sk.close()
        check("port %d on the public IP is closed from the internet" % port, closed)
    appip = ap.get("PrivateIpAddress", "")
    r = subprocess.run("curl -s --max-time 5 -o /dev/null http://%s:8000/healthz" % appip, shell=True, timeout=20)
    check("the app server private IP times out from your laptop (curl --max-time 5)", r.returncode != 0)
else:
    check("the proxy has a public IP to test", False)

print()
if failed == 0:
    print("ALL CHECKS PASSED (%d/%d)" % (passed, passed))
else:
    print("%d check(s) failed, %d passed" % (failed, passed))
sys.exit(1 if failed else 0)
