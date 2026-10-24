"""The base gateway rules for project 38, written by hand and kept apart from the case templates in
_generate.py. _generate.py imports BASE_RULES, writes it to gateway_rules.json and derives the rule
changes (the "rule pull requests") from it.

Five layers, each one reads one channel of a case:
  l1_input      user_input      patterns over what the banker typed
  l2_retrieval  retrieved_doc   patterns over a retrieved document
  l3_tools      tool_call       destination allow-list, destination keys, denied tools
  l4_egress     response        patterns over the model's answer
  l5_session    session         a memory item may only be read by the session that owns it
Internal domains in this prototype use the reserved name bank.example.
"""

BASE_RULES = {
    "name": "gateway-base",
    "normalize": True,
    "l1_input": [
        {"id": "L1-01", "pattern": r"\b(ignore|disregard|forget|discard)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,30}\b(instructions?|directives?|rules?|prompts?)\b"},
        {"id": "L1-02", "pattern": r"\b(reveal|print|show|repeat|output)\b.{0,40}\b(system prompt|hidden (prompt|instructions)|initial instructions)\b"},
        {"id": "L1-03", "pattern": r"\b(do anything now|developer mode|unrestricted mode|(?-i:DAN))\b|\b(no|without) (restrictions|limits|rules|filters)\b"},
        {"id": "L1-04", "pattern": r"\b(you are now|from now on,? you are|act as|pretend (to be|you are))\b.{0,40}\b(unrestricted|unfiltered|jailbroken|no rules|without rules)\b"},
        {"id": "L1-05", "pattern": r"\b(i am|this is)\b.{0,40}\b(head of compliance|administrator|system admin|security team)\b.{0,60}\b(override|disable|bypass|authorize|authorise)"},
        {"id": "L1-06", "pattern": r"\b(disable|bypass|turn off)\b.{0,30}\b(safety|guardrails?|filters?|checks?)\b"},
        {"id": "L1-07", "pattern": r"\bfor a (story|novel|film|screenplay|thought experiment)\b.{0,80}\b(reveal|leak|share|reads? out|print)\b.{0,60}\b(customer|account|password|prompt|client)"},
    ],
    "l2_retrieval": [
        {"id": "L2-01", "pattern": r"\b(note to|message for|attention|instruction for|directive for)\b.{0,10}\b(?:the )?(?:ai|llm|assistant|model|agent)\b"},
        {"id": "L2-02", "pattern": r"(?s)<!--.{0,200}?\b(?:ai|assistant|model|llm|instruction)\b.{0,200}?-->"},
        {"id": "L2-03", "pattern": r"(?im)^\s*(?:\[system\]|<system>|#{1,3} ?system\b|system(?: override| message| prompt)?:)"},
        {"id": "L2-04", "pattern": r"\b(?:forward|send|email|post|upload|share)\b.{0,60}\b(?:to|with|at)\b.{0,40}[\w.+-]+@(?!(?:[\w-]+\.)*bank\.example\b)[\w-]+(?:\.[\w-]+)+"},
        {"id": "L2-05", "pattern": r"\b(?:ignore|disregard|forget|set aside)\b.{0,30}\b(?:the )?(?:user|banker|question|previous instructions|prior instructions|confidentiality)\b"},
        {"id": "L2-06", "pattern": r"\bif you are (?:an? )?(?:ai|llm|language model|assistant)\b"},
        {"id": "L2-07", "pattern": r"\b(?:decode|decrypt)\b.{0,60}\b(?:and|then)\b.{0,30}\b(?:follow|execute|run|obey|apply)\b"},
        {"id": "L2-08", "pattern": r"!\[[^\]]*\]\(https?://(?![^)\s/]*\bbank\.example)[^)\s]*\?[^)\s]*\)"},
    ],
    "l3_tools": {
        "allowed_domains": ["bank.example"],
        "destination_keys": ["to", "cc", "bcc", "url", "recipients", "webhook", "destination"],
        "denied_tools": ["shell_exec", "file_delete"],
    },
    "l4_egress": [
        {"id": "L4-01", "pattern": r"\b\d{3}-\d{2}-\d{4}\b"},
        {"id": "L4-02", "pattern": r"!\[[^\]]*\]\(https?://(?![^)\s/]*\bbank\.example)[^)\s]*\?[^)\s]*\)"},
        {"id": "L4-03", "pattern": r"\b\d{10,12}\b"},
        {"id": "L4-04", "pattern": r"https?://(?![^\s/]*\bbank\.example)[^\s)]*[?&](?:ssn|dob|acct|account|name|data)="},
    ],
    "l5_session": {"enforce_owner": True},
}
