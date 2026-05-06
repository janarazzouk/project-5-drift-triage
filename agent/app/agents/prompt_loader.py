from pathlib import Path


def load_prompt(prompt_dir: Path, prompt_name: str) -> str:
    prompt_path = prompt_dir / prompt_name

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")