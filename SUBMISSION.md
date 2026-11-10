# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `terraform/` with all your `.tf` files, `deploy.sh`, `nginx/`, `systemd/clippy.service`, `README.md` and `docs/architecture.png` (or a diagram in the README)

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste the output of `terraform output` and the URL of your public site. Paste `curl -s -X POST <url>/shorten ...` and its answer.

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Show the rules of your three security groups (`terraform state show` or `aws ec2 describe-security-group-rules`). For `sg-app` and `sg-data`, why is the source a security group and not a CIDR block?

**Your answer:**

<!-- replace this line with your answer -->

### Q3. Prove the private tiers are unreachable from the internet: paste `aws ec2 describe-instances` showing no public IP on the app and data servers, and a `curl --max-time 5` to the app private IP that times out. Why can the proxy reach them but you cannot?

**Your answer:**

<!-- replace this line with your answer -->

### Q4. Run `./deploy.sh` twice and paste the end of both runs. What did you do to make the second run safe? Where do the database and Redis passwords live, and why are they not in git?

**Your answer:**

<!-- replace this line with your answer -->

### Q5. Where is your Terraform state and how is it protected (bucket versioning, locking)? What happens if two people run `terraform apply` at once?

**Your answer:**

<!-- replace this line with your answer -->

### Q6. Explain one thing that went wrong during the project: what you saw first, how you found the cause, and what you changed.

**Your answer:**

<!-- replace this line with your answer -->

### Q7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.

**Your answer:**

<!-- replace this line with your answer -->

### Q8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.

**Your answer:**

<!-- replace this line with your answer -->
