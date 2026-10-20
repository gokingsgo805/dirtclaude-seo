ANSWER_BOTS = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "Google-Extended",
    "PerplexityBot",
    "ClaudeBot",
    "Bingbot",
]


def parse_robots(txt: str) -> list[dict]:
    groups: list[dict] = []
    current = None
    for raw in (txt or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip()
        if key == "user-agent":
            if current is None or current["rules"]:
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(val.lower())
        elif key in ("allow", "disallow"):
            if not val:
                continue
            if current is None:
                current = {"agents": ["*"], "rules": []}
                groups.append(current)
            current["rules"].append({"allow": key == "allow", "path": val})
    return groups


def path_allowed(groups: list[dict], bot: str, path: str = "/") -> bool:
    name = bot.lower()
    specific = [g for g in groups if name in g["agents"]]
    star = [g for g in groups if "*" in g["agents"]]
    use = specific or star
    if not use:
        return True
    rules = [r for g in use for r in g["rules"] if r["path"] and path.startswith(r["path"])]
    if not rules:
        return True
    rules.sort(key=lambda r: (len(r["path"]), r["allow"]), reverse=True)
    best = len(rules[0]["path"])
    top = [r for r in rules if len(r["path"]) == best]
    return any(r["allow"] for r in top)


def bot_report(robots_txt: str | None, robots_status: int | None) -> list[dict]:
    if robots_txt is None or robots_status is None or robots_status >= 400:
        detail = "No robots.txt" if robots_status == 404 else "Allowed by default"
        return [{"name": name, "status": "allow", "detail": detail} for name in ANSWER_BOTS]
    groups = parse_robots(robots_txt)
    rows = []
    for name in ANSWER_BOTS:
        ok = path_allowed(groups, name, "/")
        rows.append({"name": name, "status": "allow" if ok else "block", "detail": "Allowed for /" if ok else "Disallowed for /"})
    return rows
