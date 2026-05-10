from pathlib import Path
from config import SKILLS_DIR


def load_skill(skill_path: Path) -> dict:
    """Load a single skill.md and return metadata dict."""
    content = skill_path.read_text(encoding="utf-8")
    name = skill_path.stem
    title = name
    description = ""

    lines = content.split("\n")
    in_desc = False
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            in_desc = True
            continue
        if in_desc and line.strip() and not line.startswith("#"):
            description = line.strip()
            break

    return {
        "name": name,
        "title": title,
        "description": description,
        "content": content,
        "path": str(skill_path),
    }


def load_all_skills() -> dict[str, dict]:
    """Load all *.md files from the skills/ directory."""
    skills = {}
    for p in sorted(SKILLS_DIR.glob("*.md")):
        s = load_skill(p)
        skills[s["name"]] = s
    return skills


def save_skill(name: str, content: str) -> Path:
    """Write skill content to skills/<name>.md."""
    safe = name.lower().replace(" ", "_").replace("-", "_")
    path = SKILLS_DIR / f"{safe}.md"
    path.write_text(content, encoding="utf-8")
    return path


def delete_skill(name: str) -> bool:
    """Delete skills/<name>.md. Returns True if deleted."""
    path = SKILLS_DIR / f"{name}.md"
    if path.exists():
        path.unlink()
        return True
    return False
