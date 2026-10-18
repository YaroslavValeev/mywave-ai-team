"""Run real CrewAI with a deterministic LLM inside the isolated candidate image."""

import json
import subprocess

from release_owner_runtime_20261018 import IMAGE_ID, QA, SOURCE_SHA

CODE = r"""
from crewai import Agent, Crew, Task
from crewai.llms.base_llm import BaseLLM

class LocalLLM(BaseLLM):
    def __init__(self):
        super().__init__(model="local/qualification", temperature=0)
        self.calls = 0
    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        self.calls += 1
        return "Final Answer: VERIFIED_LOCAL_CREW"
    def supports_function_calling(self):
        return False
    def supports_stop_words(self):
        return False
    def get_context_window_size(self):
        return 8192

llm = LocalLLM()
agent = Agent(role="Qualification reviewer", goal="Return the local marker",
              backstory="An isolated dependency qualification agent.", llm=llm,
              allow_delegation=False, max_iter=1, verbose=False)
task = Task(description="Return VERIFIED_LOCAL_CREW.", expected_output="VERIFIED_LOCAL_CREW", agent=agent)
result = Crew(agents=[agent], tasks=[task], memory=False, cache=False, verbose=False).kickoff()
if "VERIFIED_LOCAL_CREW" not in str(result) or not llm.calls:
    raise RuntimeError("CrewAI kickoff did not use the deterministic LLM")
print("REAL_CREWAI_LOCAL_SMOKE_PASSED", "calls=" + str(llm.calls))
"""


def main():
    proof_path = QA / "crewai-smoke.json"
    if proof_path.is_file():
        previous = json.loads(proof_path.read_text())
        if (
            previous.get("source_sha") == SOURCE_SHA
            and previous.get("image_id") == IMAGE_ID
            and previous.get("real_crewai_local_smoke_passed") is True
        ):
            print(json.dumps(previous, indent=2))
            return
    command = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/root/.cache",
        "--tmpfs",
        "/root/.local/share",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        "1",
        "--memory",
        "1g",
        "-e",
        "CREWAI_TRACING_ENABLED=false",
        "-e",
        "OTEL_SDK_DISABLED=true",
        "-e",
        "PYTHON_DOTENV_DISABLED=1",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "OPENAI_API_KEY=",
        "-e",
        "GH_TOKEN=",
        "-e",
        "GITHUB_TOKEN=",
        "-e",
        "TELEGRAM_BOT_TOKEN=",
        "--entrypoint",
        "python",
        IMAGE_ID,
        "-",
    ]
    result = subprocess.run(
        command, input=CODE.encode(), capture_output=True, timeout=180
    )
    (QA / "evidence/crewai-smoke.log").write_bytes(result.stdout + result.stderr)
    passed = (
        result.returncode == 0 and b"REAL_CREWAI_LOCAL_SMOKE_PASSED" in result.stdout
    )
    report = {
        "source_sha": SOURCE_SHA,
        "image_id": IMAGE_ID,
        "exit_code": result.returncode,
        "real_crewai_local_smoke_passed": passed,
        "external_llm_called": False,
        "app_business_pipeline_verified": False,
    }
    proof_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not passed:
        print("CrewAI qualification failed; see the private evidence log")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
