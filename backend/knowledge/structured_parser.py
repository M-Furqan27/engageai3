import re


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" -–—:\t\r\n")
    return value or None


def parse_labeled_records(
    text: str,
    labels: dict[str, list[str]],
    primary_key: str,
) -> list[dict[str, str | None]]:
    """Parse repeated structured records using deterministic ``Label: value`` fields.

    A new record starts whenever the primary label is encountered. Field values may
    continue across multiple lines until the next recognized label or record starts.
    No LLM, model call, classification, or semantic extraction is used here.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    alias_to_key: dict[str, str] = {}
    for key, aliases in labels.items():
        for alias in aliases:
            alias_to_key[alias.lower()] = key

    primary_aliases = {alias.lower() for alias in labels[primary_key]}
    record_word = next(iter(primary_aliases)).split()[0] if primary_aliases else "record"
    record_marker = re.compile(rf"^{re.escape(record_word)}\s+record\s+\d+\s*$", re.I)

    def match_label(line: str):
        if ":" not in line:
            return None
        label, value = line.split(":", 1)
        normalized = re.sub(r"\s+", " ", label).strip().lower()
        key = alias_to_key.get(normalized)
        if key is None:
            return None
        return key, value.strip(), normalized

    records: list[dict[str, str | None]] = []
    current: dict[str, str | None] | None = None
    active_key: str | None = None

    for line in lines:
        if record_marker.match(line):
            active_key = None
            continue

        matched = match_label(line)
        if matched:
            key, value, normalized_label = matched
            if normalized_label in primary_aliases:
                if current and current.get(primary_key):
                    records.append(current)
                current = {field: None for field in labels}
            elif current is None:
                # Ignore labels before the first primary field. This prevents a
                # different document type from being interpreted as this schema.
                continue

            active_key = key
            current[key] = _clean(value)
            continue

        if current is not None and active_key is not None:
            previous = current.get(active_key)
            current[active_key] = _clean(f"{previous or ''} {line}")

    if current and current.get(primary_key):
        records.append(current)

    return records


def missing_required_fields(record: dict, required_fields: tuple[str, ...]) -> list[str]:
    return [field for field in required_fields if not _clean(record.get(field))]
