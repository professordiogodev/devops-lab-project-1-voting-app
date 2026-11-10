# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `terraform/` with all your `.tf` files, `deploy.sh`, `systemd/` (one unit per service), `README.md` and a diagram in `docs/` or the README

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste `terraform output` and the URLs of the vote page and the result page. Cast a vote and paste what the result page shows, and `journalctl -u worker -n 5` from the worker server.

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Draw the path of one vote: browser, vote server, Redis, worker, PostgreSQL, result server, browser. For each arrow say the protocol, the port and which security group rule allows it.

**Your answer:**

<!-- replace this line with your answer -->

### Q3. The apps look for the hosts `redis` and `db` and for the password `postgres`. How did you make those names work on five machines, and what would you do about the password if you could not change the code? What did you try first and what went wrong?

**Your answer:**

<!-- replace this line with your answer -->

### Q4. Prove the private tiers are unreachable from the internet: show the instances without a public IP and a `curl --max-time 5` to the Redis or database private address that times out. Why can the worker reach Redis and you cannot?

**Your answer:**

<!-- replace this line with your answer -->

### Q5. Run `./deploy.sh` twice and paste the end of both. What did you do to make the second run safe? Which parts of your deployment are still manual or fragile? What would you want a tool to do for you?

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
