import re
import json
from typing import Any, Tuple, List, Dict
from .explainer import template_explain

def extract_numbers(text: str) -> List[float]:
    # Extract numbers like 10, 10.5, 91%
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    return [float(m) for m in matches]

def extract_evidence_numbers(evidence: Any) -> List[float]:
    numbers = []
    
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except:
            pass
            
    if isinstance(evidence, dict):
        for k, v in evidence.items():
            numbers.extend(extract_evidence_numbers(v))
    elif isinstance(evidence, list):
        for item in evidence:
            numbers.extend(extract_evidence_numbers(item))
    elif isinstance(evidence, (int, float)) and not isinstance(evidence, bool):
        numbers.append(float(evidence))
        
    return numbers

def is_match(num: float, evidence_numbers: List[float]) -> bool:
    for ev in evidence_numbers:
        # absolute error <= 0.1 or relative error <= 0.005
        if abs(num - ev) <= 0.1 or (ev != 0 and abs(num - ev)/abs(ev) <= 0.005):
            return True
    return False

def check(text: str, evidence: Any) -> Tuple[bool, List[float]]:
    """
    Returns (is_faithful, list_of_violations)
    """
    text_numbers = extract_numbers(text)
    evidence_numbers = extract_evidence_numbers(evidence)
    
    # We document that we ignore small bare counts (e.g. "top 3") by ignoring integers <= 5 
    # if they don't appear in evidence. This is a heuristic.
    violations = []
    
    for num in text_numbers:
        if num <= 5.0 and num.is_integer():
            continue # ignore small counts
        if not is_match(num, evidence_numbers):
            violations.append(num)
            
    return (len(violations) == 0, violations)

def generate_faithful_explanation(evidence: Any, hypotheses: List[Dict], actions: List[Any], original_explain_func) -> Dict[str, Any]:
    # Try first
    result = original_explain_func(evidence, hypotheses, actions)
    result_text = json.dumps(result)
    
    ok, violations = check(result_text, evidence)
    if ok:
        return result
        
    # Regenerate once
    # In a real implementation we would pass the violations back to the LLM. 
    # For now, we will just call it again, perhaps it succeeds.
    # To truly pass it back we'd alter the prompt.
    result = original_explain_func(evidence, hypotheses, actions)
    result_text = json.dumps(result)
    
    ok, violations = check(result_text, evidence)
    if ok:
        return result
        
    # Still fails -> template fallback
    return template_explain(evidence, hypotheses, actions)
