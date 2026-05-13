import re
import json
import os
import hashlib
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv


class IncidentPipeline:

    def __init__(self, api_key):

        # Configure Gemini
        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel("gemini-2.5-flash")

        self.llm_log_path = "llm_calls.jsonl"

        self.log_pattern = re.compile(
            r'^\[(?P<timestamp>.*?)\]\s+(?P<level>\w+)\s+(?P<service>[\w-]+)\s+(?P<message>.*)$'
        )

        self.field_extractors = {
            "query_id": r'query_id=(q_\d+)',
            "duration_ms": r'duration=(\d+)ms',
            "duration_seconds": r'duration=(\d+)s',
            "table": r'table=([\w_]+)',
            "pool_size": r'pool_size=(\d+)',
            "waiting": r'waiting=(\d+)',
            "job_name": r'batch job ([\w_]+)'
        }

        os.makedirs("parsed_logs", exist_ok=True)

    # ---------------------------------------------------
    # Parse log file
    # ---------------------------------------------------

    def parse_log_file(self, file_path):

        records = []

        with open(file_path, "r") as f:

            for line in f:

                match = self.log_pattern.match(line)

                if match:

                    record = match.groupdict()

                    for field, pattern in self.field_extractors.items():

                        found = re.search(pattern, line)

                        if found:
                            record[field] = found.group(1)

                    records.append(record)

        return records

    # ---------------------------------------------------
    # Log LLM calls
    # ---------------------------------------------------

    def log_llm_call(self, stage, incident_id, prompt, output_path):

        record = {
            "stage": stage,
            "incident_id": incident_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": "Google",
            "model": "gemini-2.5-flash",
            "prompt_hash": hashlib.md5(prompt.encode()).hexdigest(),
            "input_artifacts": (
                [f"parsed_logs/{incident_id}.json"]
                if incident_id
                else ["timelines.json"]
            ),
            "output_artifact": output_path
        }

        with open(self.llm_log_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    # ---------------------------------------------------
    # Gemini helper
    # ---------------------------------------------------

    def _call_gemini_json(self, prompt):

        response = self.model.generate_content(prompt)

        text = response.text.strip()

        # Remove markdown code blocks
        clean_json = re.sub(
            r'^```json\s*|```$',
            '',
            text,
            flags=re.MULTILINE
        ).strip()

        try:
            return json.loads(clean_json)

        except json.JSONDecodeError as e:

            print("JSON Decode Error:", e)

            # Try extracting JSON block
            maybe_json = re.search(
                r'(\{.*\}|\[.*\])',
                clean_json,
                re.DOTALL
            )

            if maybe_json:

                try:
                    return json.loads(maybe_json.group(0))

                except:
                    return {}

            return {}

    # ---------------------------------------------------
    # Compute metrics
    # ---------------------------------------------------

    def compute_metrics(self, incident_id, records):

        first_warning = next(
            (
                r['timestamp']
                for r in records
                if r['level'] in ['WARN', 'ERROR']
            ),
            None
        )

        impact_moment = next(
            (
                r['timestamp']
                for r in records
                if r['level'] == 'CRIT'
            ),
            None
        )

        recovery_entry = next(
            (
                r for r in reversed(records)
                if any(
                    k in r['message']
                    for k in ["resumed", "CLOSED", "recovering"]
                )
            ),
            None
        )

        recovery_timestamp = (
            recovery_entry['timestamp']
            if recovery_entry
            else None
        )

        mttr = None

        if impact_moment and recovery_timestamp:

            fmt = "%Y-%m-%d %H:%M:%S %Z"

            try:
                mttr = int(
                    (
                        datetime.strptime(recovery_timestamp, fmt)
                        - datetime.strptime(impact_moment, fmt)
                    ).total_seconds() / 60
                )

            except:
                mttr = None

        return {
            "first_warning": first_warning,
            "impact_moment": impact_moment,
            "recovery_timestamp": recovery_timestamp,
            "mttr_minutes": mttr
        }

    # ---------------------------------------------------
    # Timeline reconstruction
    # ---------------------------------------------------

    def reconstruct_timeline(self, incident_id):

        with open(f'parsed_logs/{incident_id}.json', 'r') as f:
            logs = json.load(f)

        prompt = f"""
        Return ONLY valid JSON.

        Create a causal timeline from these logs:

        {json.dumps(logs)}

        Include:
        - incident_id
        - first_symptom
        - impact_moment
        - resolution_trigger
        - timeline (array of timestamp, event, causal_significance)
        """

        result = self._call_gemini_json(prompt)

        self.log_llm_call(
            "TIMELINES_RECONSTRUCTED",
            incident_id,
            prompt,
            "timelines.json"
        )

        return result

    # ---------------------------------------------------
    # Root cause analysis
    # ---------------------------------------------------

    def analyze_root_causes(self, timelines):

        with open('data/historical_incidents.json', 'r') as f:
            history = json.load(f)

        prompt = f"""
        Return ONLY valid JSON.

        Analyze these timelines:

        {json.dumps(timelines)}

        Against this history:

        {json.dumps(history)}

        Return:
        - root causes
        - same_failure_mode (boolean)
        - structured_justification
        """

        result = self._call_gemini_json(prompt)

        self.log_llm_call(
            "ROOT_CAUSES_ANALYSED",
            None,
            prompt,
            "root_cause_analysis.json"
        )

        return result

    # ---------------------------------------------------
    # Generate postmortem
    # ---------------------------------------------------

    def generate_postmortem(self, incident_id, timelines, rca):

        prompt = f"""
        Generate a formal Markdown post-mortem.

        Incident ID:
        {incident_id}

        Timeline:
        {json.dumps(timelines[incident_id])}

        RCA:
        {json.dumps(rca)}

        Action items MUST reference specific services/tables.
        """

        response = self.model.generate_content(prompt)

        output_path = f"postmortem_{incident_id[-1]}.md"

        with open(output_path, 'w') as f:
            f.write(response.text)

        self.log_llm_call(
            "POSTMORTEMS_GENERATED",
            incident_id,
            prompt,
            output_path
        )

    # ---------------------------------------------------
    # Systemic actions
    # ---------------------------------------------------

    def identify_systemic_actions(self):

        with open('postmortem_a.md', 'r') as f:
            a = f.read()

        with open('postmortem_b.md', 'r') as f:
            b = f.read()

        prompt = f"""
        Based on these two postmortems,
        identify SHARED systemic action items.

        Postmortem A:
        {a}

        Postmortem B:
        {b}
        """

        response = self.model.generate_content(prompt)

        with open("systemic_actions.md", "w") as f:
            f.write(response.text)

        self.log_llm_call(
            "SYSTEMIC_ACTIONS_IDENTIFIED",
            None,
            prompt,
            "systemic_actions.md"
        )

    # ---------------------------------------------------
    # Run pipeline
    # ---------------------------------------------------

    def run(self):

        metrics_store = {}

        # Step 1 + 2
        for inc in ["incident_a", "incident_b"]:

            recs = self.parse_log_file(f"data/{inc}.log")

            with open(f"parsed_logs/{inc}.json", "w") as f:
                json.dump(recs, f, indent=4)

            metrics_store[inc] = self.compute_metrics(inc, recs)

        with open("incident_metrics.json", "w") as f:
            json.dump(metrics_store, f, indent=4)

        # Step 3
        timeline_a = self.reconstruct_timeline("incident_a")
        timeline_b = self.reconstruct_timeline("incident_b")

        all_timelines = {
            "incident_a": timeline_a,
            "incident_b": timeline_b
        }

        with open("timelines.json", "w") as f:
            json.dump(all_timelines, f, indent=4)

        # Step 4
        rca_data = self.analyze_root_causes(all_timelines)

        with open("root_cause_analysis.json", "w") as f:
            json.dump(rca_data, f, indent=4)

        # Step 5
        self.generate_postmortem(
            "incident_a",
            all_timelines,
            rca_data
        )

        self.generate_postmortem(
            "incident_b",
            all_timelines,
            rca_data
        )

        # Step 6
        self.identify_systemic_actions()


# ---------------------------------------------------
# Main
# ---------------------------------------------------

if __name__ == "__main__":

    load_dotenv()

    MY_KEY = os.getenv("GEMINI_API_KEY")

    if not MY_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env")

    pipeline = IncidentPipeline(api_key=MY_KEY)

    pipeline.run()