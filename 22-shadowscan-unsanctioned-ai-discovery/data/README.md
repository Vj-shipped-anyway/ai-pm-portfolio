# Sample Data — ShadowScan walkthrough

Eight CSV files drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261022` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, product, vendor, domain or log. Every domain is invented and ends in `.example`. The logs are produced by the generator, not by a proxy, a resolver or a model.**

**The truth is known because the data is synthetic.** The generator decides which domains are AI tools nobody approved, which sessions on an approved product use an AI feature, which names only look like AI tools, and which sessions happen on a personal device. A real estate does not hand you that; the first job in a real deployment is capturing real proxy and DNS logs and a real catalog.

The headline scenario the walkthrough resolves: **a modeled bank has a catalog of 12 approved tools. Over two weeks its proxy and DNS logs hold 4,200 sessions on 30 unsanctioned AI domains and 1,200 sessions that use an AI feature inside an approved product. Another 600 sessions happen on personal devices and appear in no log. A static blocklist finds 2,275 of the 4,200. ShadowScan finds 3,948, ranks what it finds by data exposure, and leaves the 600 invisible.**

---

## Seed, parameters and what was changed

- **Seed.** `20261022` was picked before the first run. No other seed was tried.
- **Parameters.** The traffic mix, the popularity of each domain, the byte sizes per kind of tool, the path styles and which domains sit in the feed and on the blocklist were set from design reasoning before any result was computed. The design: chat tools send short prompts (a few KB) and read long answers; document and audio tools send large files and read short answers; code tools sit in between; the upload and generation tools are used mostly by the departments that handle sensitive data; popularity is set by hand and is independent of whether the blocklist knows the domain, except that the oldest domains had a head start.
- **One change after the first run.** After the first run of step 1, the first version put nearly every member of staff in the group that uses AI outside the catalog. I judged that not credible even for a dense test set, so I added `ADOPTER_SHARE` (two in five staff use AI beyond the catalog at all) and narrowed the user pools per tool (`pool_k`). Steps 2 to 4 had not been run on any version of the data at that point, and nothing has been changed since. The folder README points here for this note.
- **Not tuned.** No parameter was adjusted to make a result look better. Two outcomes look unflattering for the new layer and were left as they came out: ShadowScan raises false positives on two benign domains, and it finds only 40.9% of the AI-feature sessions inside approved SaaS.
- **This is a test set.** It is dense on purpose so that every effect appears often enough to count. It is not an estimate of how often real staff use AI tools, how large real logs are, or how a real blocklist performs.

---

## `dept_sensitivity.csv` — 10 departments

The sensitivity weight is an assumption of a modeled bank, on a scale of 1 to 5. It is not a rating of any real department.

```
dept,dept_name,sensitivity_weight
LEG,Legal and Compliance,5
CRD,Credit Underwriting,5
WLT,Wealth Advisory,4
FIN,Finance and Treasury,4
HRP,People and HR,4
FRD,Fraud and Financial Crime,4
ENG,Technology and Engineering,3
OPS,Operations and Servicing,3
MKT,Marketing and Communications,2
FAC,Facilities and Procurement,1
```

## `users.csv` — 520 staff

| Column | What it is |
| --- | --- |
| `user_id` | `U0001` onward. |
| `dept` | Department code. |
| `site` | `hq` (headquarters; traffic goes through the proxy) or `branch` (only DNS logging covers it). |

```
user_id,dept,site
U0001,LEG,hq
U0002,LEG,hq
U0003,LEG,hq
```

## `sanctioned_catalog.csv` — 12 approved tools

| Column | What it is |
| --- | --- |
| `tool` | An invented tool name. `S-` tools are approved as AI tools; `P-` tools are approved as ordinary software. |
| `domains` | Registered domains, semicolon-separated. A host matches when it equals the domain or ends in `.` plus the domain. |
| `approved_data_class` | The data class the approval covers. |
| `ai_in_scope` | `yes` if the AI behavior was part of the review, `no` if the product was approved as ordinary software and its AI features were not assessed. |
| `use_case` | The job the tool does, used to suggest an approved alternative. |

```
tool,domains,approved_data_class,ai_in_scope,use_case
S-01 Enterprise chat assistant,assist-s01.example,Confidential,yes,chat
S-02 Code assistant,codehelp-s02.example,Internal,yes,code
S-03 Meeting notes summarizer,notes-s03.example,Internal,yes,transcribe
S-04 Translation assistant,translate-s04.example,Public,yes,translate
S-05 Document summarizer,summarize-s05.example,Confidential,yes,document
S-06 Research assistant,research-s06.example,Public,yes,chat
S-07 Knowledge base search,knowledge-s07.example,Confidential,yes,chat
P-01 Document suite,docs-p01.example,Confidential,no,saas
P-02 CRM,crm-p02.example,Confidential,no,saas
P-03 Service desk,desk-p03.example,Internal,no,saas
P-04 Meetings and video,meet-p04.example,Internal,no,saas
P-05 HR portal,people-p05.example;hrdocs-p05.example,Restricted,no,saas
```

## `known_ai_domains.csv` — 40 domains (a feed that is partly out of date)

`domain, category`. It lists the sanctioned AI tools, 22 of the 30 unsanctioned AI domains and 11 retired services. 8 unsanctioned AI domains are absent from it, which is what makes it stale.

```
domain,category
artspark-u24.example,image
askpilot-u02.example,chat
assist-s01.example,chat
briefreader-u11.example,document
callsummary-ai-u29.example,transcribe
chatnest-u04.example,chat
codehelp-s02.example,code
```

## `blocklist.csv` — 15 entries (a static list)

`entry, match_type`. An exact entry matches a host or any subdomain. A keyword entry matches a substring of the host name. 4 of the 13 exact entries are retired domains that match no traffic.

```
entry,match_type
talkwise-u01.example,domain
askpilot-u02.example,domain
quickai-u03.example,domain
chatnest-u04.example,domain
pdfchat-u09.example,domain
docsense-u10.example,domain
codepal-u17.example,domain
pixelforge-u22.example,domain
voicenote-u26.example,domain
oldchat-b01.example,domain
oldchat-b02.example,domain
oldchat-b03.example,domain
oldchat-b04.example,domain
ai,keyword
llm,keyword
```

## `proxy_log.csv` — 15,000 sessions seen by the proxy

One row is one session: a user reaching a host in an hour. Headquarters staff only.

| Column | What it is |
| --- | --- |
| `hour` | Hour index since the start of a 14-day window; hour 0 is Monday 00:00. Weighted to weekday business hours. |
| `user_id`, `dept` | Who, and the department (from the directory). |
| `domain` | The host, sometimes with an `api.` or `app.` prefix. |
| `path` | The URL path, or `-` when the client does not expose it (pinned desktop apps and mobile clients, which a proxy cannot inspect). |
| `bytes_out`, `bytes_in` | Bytes the client sent and received. Bytes out is what the client sent, whether or not a block page came back; this prototype does not model blocking. |
| `client_class` | `browser`, `desktop_app`, `script` or `mobile_mdm`. |

## `dns_log.csv` — 7,500 lookups seen by DNS only

`hour, user_id, domain`. Branch staff only. No path, no sizes. This is the point of one of the six deficiencies: a name is visible and the volume is not.

## `truth_sessions.csv` — the label of every log row, and 600 sessions no log shows

| Column | What it is |
| --- | --- |
| `session_id` | `P<n>` is the n-th row of `proxy_log.csv`; `D<n>` is the n-th row of `dns_log.csv`; `X<n>` is a session no log shows. |
| `true_label` | `sanctioned_ai`, `unsanctioned_ai`, `embedded_ai_in_approved_saas`, `benign_lookalike`, `other` or `off_network`. |
| `true_bytes_out` | The bytes the session sent. Empty for proxy rows (the log has it); filled for DNS rows and off-network sessions. |
| `user_id`, `domain` | Filled only for `off_network` rows, which have no log row to join to. |

For the first 15,000 data rows, line `k` of `truth_sessions.csv` labels line `k` of `proxy_log.csv` (both files have one header line). A few rows, proxy lines first and then the truth lines for the same sessions:

```
hour,user_id,dept,domain,path,bytes_out,bytes_in,client_class
0,U0495,FAC,assist-s01.example,/app,3428,16710,browser
3,U0175,FIN,app.crm-p02.example,/labs/quick-draft,8669,35152,browser
6,U0152,FIN,maintenance-log-l02.example,/home,2516,11406,browser
7,U0355,ENG,refactorly-u20.example,/v1/completions,68286,4143,desktop_app
7,U0492,FAC,docs-p01.example,/api/v2/assist/summarize,25603,17485,browser
7,U0510,FAC,pdfchat-u09.example,/chat-with-doc/1589,491691,3531,browser
9,U0181,FIN,filevault-f01.example,/upload,326846,2388,browser
```

```
session_id,true_label,true_bytes_out,user_id,domain
P7,sanctioned_ai,,,
P18,embedded_ai_in_approved_saas,,,
P35,benign_lookalike,,,
P60,unsanctioned_ai,,,
P72,embedded_ai_in_approved_saas,,,
P74,unsanctioned_ai,,,
P169,other,,,
```

A DNS row and an off-network row, from the same file:

```
hour,user_id,domain
7,U0215,contract-ai-u12.example
```

```
session_id,true_label,true_bytes_out,user_id,domain
D27,unsanctioned_ai,660902,,
X1,off_network,7950,U0002,askpilot-u02.example
X2,off_network,2537490,U0002,briefreader-u11.example
X3,off_network,670121,U0002,callsummary-ai-u29.example
```

Truth by label, over the 22,500 log rows: 3,050 sanctioned AI, 4,200 unsanctioned AI (3,000 proxy and 1,200 DNS), 1,200 AI-feature sessions inside approved SaaS (900 and 300), 1,150 benign look-alike names (800 and 350) and 12,900 other. Plus 600 off-network sessions.

---

## What the generator decides

- **Unsanctioned AI domains (30).** Five kinds of tool: chat, document upload, code, image and transcription. Each has its own sizes and path style. 22 are in the feed; 9 are exact entries on the blocklist; 6 have `ai` in the name, which the blocklist's keyword rule hits. 8 are in neither list, and of those 2 are built to be invisible to the rules: a chat tool and a code tool on plain paths with small payloads.
- **AI features inside approved SaaS (5 products).** Some sessions on an approved product use an AI feature. Most of those use a generation-style path; some use a vendor-specific path that no pattern matches.
- **Benign look-alikes (10).** Every name contains `ai` as part of an ordinary word and none is an AI service.
- **Other traffic.** Ordinary use of the approved products, general web, internal portals, two kinds of benign page that fool the heuristics (a reports page whose path says `generate`, and file shares with large uploads), and the benign path on two approved products that looks like generation.
- **Hidden paths.** Pinned desktop apps and mobile clients show the proxy no path, so only domain and sizes are seen.
- **Off-network (600).** Sessions on personal devices, in the evening and on Saturdays and Sundays, on the unsanctioned domains. They have no log row.
- **Who uses what.** Two in five staff are adopters of AI tools beyond the catalog; each tool draws its users from a pool of adopters weighted by department (documents and uploads skew to the sensitive departments, code to engineering, images to marketing).

The thresholds ShadowScan applies (the path pattern, the size ratio, the discovery rule, the next-action rules) live in `src/step_04_with_shadowscan.py` and are assumptions of a modeled bank, not advice.
