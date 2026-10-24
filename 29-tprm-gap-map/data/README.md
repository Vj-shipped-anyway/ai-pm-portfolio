# Data for project 29

Synthetic. `_generate.py` uses a fixed seed, so a rerun reproduces every generated file byte for byte. Nothing here comes from a real vendor, bank or employer. The hazard rates in `_generate.py` are my assumptions, fixed before the first run.

| File | What it holds |
|---|---|
| `vendors.csv` | 60 vendors. `service_type` (core_processing, cloud_hosting, compliance_tool, fintech_partner, data_provider, ai_enabled_service, call_center, facilities), `activity_share_pct`, `upstream_provider` (P1 to P4 model providers, C1 to C3 clouds), `model_change_notice_days`, `trains_on_bank_data`, `bank_data_retained_days` (AI-enabled only), and four due-diligence documents on file (`soc_report`, `insurance`, `financial_ok`, `key_personnel`) |
| `incident_log.csv` | 100 simulated incidents over 36 months: `vendor_id`, `month`, `cause` (own_outage, upstream_outage, silent_model_change, data_exposure), `customer_impact_hours`, `material` (4 hours or more) |
| `vendor_truth.csv` | Per vendor: whether it had a material incident and the causes. This is the label the tiering is scored against, derived from the log, not from the tiering rules |
| `guidance_map.csv` | Hand-written, not generated: 16 rows mapping the proposed guidance to evidence for an AI-enabled vendor, with the section of the proposal Labels in `how_the_text_prompts_it`: named, the text lists the item; principle, only a general principle covers it; example, the text offers it as an illustration; not mentioned, the text has nothing on it. |

To run it on your own data, keep the column names of `vendors.csv` and `incident_log.csv`.
