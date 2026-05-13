import os
import json

def validate():
    required_files = [
        'parsed_logs/incident_a.json', 
        'parsed_logs/incident_b.json',
        'incident_metrics.json',
        'timelines.json',
        'root_cause_analysis.json',
        'postmortem_a.md',
        'postmortem_b.md',
        'systemic_actions.md',
        'llm_calls.jsonl'
    ]
    
    print("--- Running Validation ---")
    for f in required_files:
        if os.path.exists(f):
            print(f"[PASS] Found {f}")
        else:
            print(f"[FAIL] Missing {f}")

    # Check JSON validity of metrics
    try:
        with open('incident_metrics.json', 'r') as f:
            metrics = json.load(f)
            if 'incident_a' in metrics and 'mttr_minutes' in metrics['incident_a']:
                print("[PASS] Incident metrics are valid and computed.")
    except Exception as e:
        print(f"[FAIL] Metrics validation error: {e}")

if __name__ == "__main__":
    validate()