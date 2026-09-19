"""
Prompt construction for the Gemini Root Cause Reasoning Engine.
Formats specialist agent findings into an epistemically clear prompt and injects AI safety constraints.
"""

import json
from backend.reasoning.schemas import ReasoningContextInput

SYSTEM_INSTRUCTION = """
You are the Root Cause Reasoning Engine for an automated VFX Pipeline Incident Platform.
Your purpose is to synthesize heterogeneous evidence across Render QA, Hardware Diagnostics,
Asset Validation, and Historical Evidence agents to determine the singular root cause of an incident.

CRITICAL AI SAFETY RULES:
1. NEVER FABRICATE EVIDENCE: Every supporting and contradicting evidence string you cite MUST originate directly from the supplied specialist agent findings or incident event. Never invent log snippets, telemetry percentages, or file paths.
2. NO PRODUCTION EXECUTION: You are strictly an analytical reasoning layer. Do not generate commands or attempt to execute tools.
3. NO FALSE CERTAINTY: Do not convert uncertainty into certainty. If findings conflict or evidence is weak, lower your confidence score accordingly.
4. INSUFFICIENT EVIDENCE HANDLING: If the input contains no specialist findings, unverified assumptions, or insufficient diagnostic data to draw a definitive conclusion, you MUST set:
   - root_cause: "INSUFFICIENT_EVIDENCE"
   - confidence: < 0.5
   - recommended_action: "DISPATCH_INVESTIGATION_MANUAL"
5. CONTRADICTORY EVIDENCE: Explicitly state evidence that contradicts competing hypotheses (e.g., if GPU memory was 99.6% full, note that hardware was healthy and disk space was not exhausted, contradicting storage or thermal faults).
6. STRICT JSON COMPLIANCE: Output strictly according to the provided schema.
""".strip()


def build_reasoning_prompt(context: ReasoningContextInput) -> str:
    """Constructs the prompt detailing the incident and all specialist findings."""
    inc = context.incident
    rqa = context.render_qa_findings
    hw = context.hardware_findings
    asset = context.asset_findings
    hist = context.historical_evidence or {}

    sections: list[str] = []

    # 1. Incident Overview
    sections.append("=== SECTION 1: CANONICAL INCIDENT OVERVIEW ===")
    sections.append(f"Incident / Event ID: {inc.get('event_id') or inc.get('incident_id') or 'N/A'}")
    sections.append(f"Event Type: {inc.get('event_type')}")
    sections.append(f"Severity: {inc.get('severity')}")
    sections.append(f"Source System: {inc.get('source') or inc.get('source_system')}")
    sections.append(f"Project / Shot: {inc.get('project')}/{inc.get('shot')}")
    sections.append(f"Error Details: {json.dumps(inc.get('error_details', {}))}")
    if inc.get("entity"):
        sections.append(f"Entity Details: {json.dumps(inc.get('entity', {}))}")

    # 2. Render QA Findings
    sections.append("\n=== SECTION 2: RENDER QA SPECIALIST FINDINGS ===")
    if not rqa:
        sections.append("No Render QA findings provided.")
    else:
        for idx, f in enumerate(rqa):
            sections.append(f"[{idx + 1}] Type: {f.get('finding_type')}, Severity: {f.get('severity')}, Confidence: {f.get('confidence')}")
            sections.append(f"    Description: {f.get('description') or f.get('title')}")
            if f.get("observed"):
                sections.append(f"    Observed: {'; '.join(f.get('observed'))}")
            if f.get("inferred"):
                sections.append(f"    Inferred: {'; '.join(f.get('inferred'))}")
            if f.get("unknown"):
                sections.append(f"    Unknown: {'; '.join(f.get('unknown'))}")
            if f.get("evidence"):
                sections.append(f"    Evidence: {f.get('evidence')}")

    # 3. Hardware Diagnostics Findings
    sections.append("\n=== SECTION 3: HARDWARE DIAGNOSTIC SPECIALIST FINDINGS ===")
    if not hw:
        sections.append("No Hardware Diagnostic findings provided.")
    else:
        for idx, f in enumerate(hw):
            sections.append(f"[{idx + 1}] Type: {f.get('finding_type')}, Severity: {f.get('severity')}, Confidence: {f.get('confidence')}")
            if f.get("evidence"):
                sections.append(f"    Evidence: {'; '.join(f.get('evidence'))}")
            if f.get("observed"):
                sections.append(f"    Observed: {'; '.join(f.get('observed'))}")
            if f.get("inferred"):
                sections.append(f"    Inferred: {'; '.join(f.get('inferred'))}")
            if f.get("details"):
                sections.append(f"    Details: {json.dumps(f.get('details'))}")

    # 4. Asset Validation Findings
    sections.append("\n=== SECTION 4: ASSET VALIDATION SPECIALIST FINDINGS ===")
    if not asset:
        sections.append("No Asset Validation findings provided.")
    else:
        for idx, f in enumerate(asset):
            sections.append(f"[{idx + 1}] Type: {f.get('finding_type')}, Severity: {f.get('severity')}, Confidence: {f.get('confidence')}")
            if f.get("evidence"):
                sections.append(f"    Evidence: {'; '.join(f.get('evidence'))}")
            if f.get("dependency_chain"):
                sections.append(f"    Dependency Chain: {' -> '.join(f.get('dependency_chain'))}")
            if f.get("observed"):
                sections.append(f"    Observed: {'; '.join(f.get('observed'))}")

    # 5. Historical Evidence & Precedents
    sections.append("\n=== SECTION 5: HISTORICAL EVIDENCE & PRECEDENTS ===")
    if not hist:
        sections.append("No Historical Evidence provided.")
    else:
        sections.append(f"Historical Precedents Found: {len(hist.get('similar_incidents', []))} similar incidents.")
        for p in hist.get("recommended_precedents", []):
            sections.append(
                f"    Precedent Strategy: {p.get('strategy')} "
                f"({p.get('success_count')}/{p.get('sample_size')} successes, {p.get('success_rate', 0) * 100:.1f}% rate)"
            )
            for c in p.get("caveats", []):
                sections.append(f"      Caveat: {c}")

    # 6. Final Instructions
    sections.append("\n=== SECTION 6: INSTRUCTIONS ===")
    sections.append("Synthesize the findings above into a singular RootCauseAnalysis.")
    sections.append("1. Determine the root cause (or 'INSUFFICIENT_EVIDENCE').")
    sections.append("2. Extract supporting evidence strictly from the text above.")
    sections.append("3. Extract contradicting evidence that disproves alternative theories.")
    sections.append("4. List evaluated alternative causes and explain why they are less likely.")
    sections.append("5. Recommend a concrete remediation action.")

    return "\n".join(sections)
