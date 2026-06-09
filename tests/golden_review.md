# Golden Set: Expected Triage Decisions

Auto-seeded from the most recent `output/output.json`. Review each email below 
and flag any decision you'd grade differently. Corrections should be applied to 
`tests/golden.json` (the regression test reads from there).

Fields checked: `category`, `priority`, `has_deadline`, `portco_problem_flagged`, 
and whether each Step 2 action fired (`reply_draft`, `deadline`, `next_steps`).

Not checked: the generative outputs (rationale, summary, reply text, next-step text). 
Those have natural model variance and are evaluated separately by the LLM grader.

---

### Email #1
**From:** mark.chen@horizoncapital.com  
**Subject:** Re: Series B interest — CloudOps AI

> Following up on our conversation from last week. We've completed initial diligence and our partners are aligned on moving forward. Can we schedule a call this week to discuss term sheet timing?

- **Category:** Deal Flow
- **Priority:** High
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft, deadline

---

### Email #2
**From:** sarah.williams@portfolioco.com  
**Subject:** Q1 Operating Update — Momentum Software

> Hi team, attached is our Q1 board pack. Revenue came in at $4.2M, up 18% QoQ. We missed EBITDA by about 8% due to a one-time infrastructure migration cost. Happy to walk through on our next call.

- **Category:** Portfolio Update
- **Priority:** Medium or Low _(borderline, either accepted)_
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** _(none, marked as read)_

---

### Email #3
**From:** james.thornton@lpfund.com  
**Subject:** Capital Call Notice Question

> We received the capital call notice dated April 28th. Can you confirm the wire instructions and deadline? We want to make sure we process this on time.

- **Category:** LP Communication
- **Priority:** High or Medium _(borderline, either accepted)_
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft _(borderline, either fires or doesn't)_

---

### Email #4
**From:** recruiter@talentfirm.com  
**Subject:** Top CFO candidates for your review

> Hi, I wanted to share three CFO profiles that match the criteria we discussed. All three have PE-backed company experience. Let me know when you'd like to set up screenings.

- **Category:** Other
- **Priority:** Low
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** _(none, marked as read)_

---

### Email #5
**From:** david.park@internalteam.com  
**Subject:** Team offsite — dates and logistics

> Hey, locking in the offsite for June 12-13 in the Hamptons. Can everyone confirm availability by EOW? I'll send hotel info once we have a headcount.

- **Category:** Internal
- **Priority:** Low
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** deadline

---

### Email #6
**From:** angela.ross@venturebridge.com  
**Subject:** New deal — B2B SaaS, $8M ARR, logistics vertical

> Wanted to get this in front of you before we go broad. Logistics SaaS company, $8M ARR, growing 35% YoY, founder looking for a growth equity partner. Happy to send the deck if there's interest.

- **Category:** Deal Flow
- **Priority:** Medium
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** _(none, marked as read)_

---

### Email #7
**From:** tom.nguyen@alphaportfolio.com  
**Subject:** Leadership transition at RetailTech Co

> Wanted to flag that our CEO submitted her resignation this morning effective in 30 days. The board is meeting Friday to discuss interim options. Will keep you posted.

- **Category:** Portfolio Update
- **Priority:** High
- **has_deadline:** True
- **portco_problem_flagged:** True
- **Actions fired:** reply_draft, deadline, next_steps

---

### Email #8
**From:** compliance@regulatorywatch.com  
**Subject:** New SEC disclosure requirements — action required by June 30

> A reminder that new SEC rules affecting private fund advisers take effect June 30th. Your compliance team should review the updated Form PF requirements. Please confirm receipt.

- **Category:** Compliance
- **Priority:** High or Medium _(borderline, either accepted)_
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft _(borderline, either fires or doesn't)_, deadline

---

### Email #9
**From:** lisa.park@mountainviewlp.com  
**Subject:** Quarterly performance review request

> Hi, we're preparing our Q1 LP report and wanted to request updated performance metrics across your current fund. Specifically IRR, MOIC, and DPI by portfolio company if available. Deadline is May 20th.

- **Category:** LP Communication
- **Priority:** High
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft, deadline

---

### Email #10
**From:** noreply@docusign.com  
**Subject:** Document ready for signature — NDA with Apex Growth Partners

> Alex Carter, a document has been sent to you for electronic signature. Please review and sign at your earliest convenience.

- **Category:** Deal Flow
- **Priority:** High or Medium _(borderline, either accepted)_
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft _(borderline, either fires or doesn't)_

---

### Email #11
**From:** kevin.shaw@apexgrowth.com  
**Subject:** Follow-up — NDA and next steps

> Just wanted to make sure you received the NDA from DocuSign. Once that's executed we can share the CIM. We have two other parties engaged so want to keep things moving.

- **Category:** Deal Flow
- **Priority:** High
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft

---

### Email #12
**From:** priya.mehta@internalteam.com  
**Subject:** Updated financial model — please review before Thursday

> Hi, I've attached the revised model with the updated revenue assumptions we discussed. Can you take a look before the partner meeting Thursday? A few of the scenarios still need your input on the exit multiple range.

- **Category:** Internal
- **Priority:** Medium
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** deadline

---

### Email #13
**From:** robert.klein@creditsuisse.com  
**Subject:** Debt financing options for portfolio company acquisition

> Following our call, I've put together three financing structures for the proposed add-on acquisition. Happy to walk through the pros and cons on a call this week. Let me know your availability.

- **Category:** Deal Flow
- **Priority:** High
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft, deadline

---

### Email #14
**From:** anna.steele@harborcapital.com  
**Subject:** Re: Co-investment opportunity — HealthTech Platform

> We've reviewed the materials and our team is supportive of co-investing up to $5M alongside your fund. Can we get on a call to align on timing and documentation before the close?

- **Category:** Deal Flow
- **Priority:** High
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft

---

### Email #15
**From:** events@peconference.com  
**Subject:** Speaker invitation — Private Equity Innovation Summit 2026

> We'd like to invite you to speak on a panel at this year's PE Innovation Summit in Chicago on September 18th. The panel topic is AI adoption in middle market PE. Please let us know by June 1st if you're available.

- **Category:** Other
- **Priority:** Low
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** deadline

---

### Email #16
**From:** michael.ford@portfolioco.com  
**Subject:** Urgent — customer churn spike in April

> Wanted to flag this before the board call. We saw an unexpected 12% churn spike in April concentrated in our SMB segment. We believe it's tied to a pricing change we rolled out in March. Working on a response plan now.

- **Category:** Portfolio Update
- **Priority:** High
- **has_deadline:** False
- **portco_problem_flagged:** True
- **Actions fired:** reply_draft, next_steps

---

### Email #17
**From:** jennifer.wu@internalteam.com  
**Subject:** Expense report approvals pending

> Hi, there are four expense reports sitting in the queue waiting for your approval. Oldest one is from April 22nd. Can you take a look when you get a chance?

- **Category:** Internal
- **Priority:** Low
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** _(none, marked as read)_

---

### Email #18
**From:** dan.okafor@lpfund.com  
**Subject:** Fund III commitment — increasing allocation

> After our recent conversation I've been authorized to increase our Fund III commitment from $25M to $40M. Please send updated subscription documents when ready.

- **Category:** LP Communication
- **Priority:** High or Medium _(borderline, either accepted)_
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** reply_draft _(borderline, either fires or doesn't)_

---

### Email #19
**From:** press@techcrunch.com  
**Subject:** Comment request — story on AI adoption in private equity

> Hi Alex, I'm a reporter at TechCrunch working on a piece about how PE firms are adopting AI internally. Would love a quick comment or a 15-minute call before Friday. No obligation.

- **Category:** Press
- **Priority:** Low
- **has_deadline:** True
- **portco_problem_flagged:** False
- **Actions fired:** deadline

---

### Email #20
**From:** alex.turner@portfolioco.com  
**Subject:** Board meeting prep — deck and materials

> Sending over the board deck for next week's meeting. Still waiting on the legal update from outside counsel. Will send that separately once it comes in. Let me know if anything looks off.

- **Category:** Portfolio Update
- **Priority:** Medium
- **has_deadline:** False
- **portco_problem_flagged:** False
- **Actions fired:** _(none, marked as read)_

---
