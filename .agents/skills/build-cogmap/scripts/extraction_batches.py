"""Shared extraction batching and output validation."""
import hashlib
import json
import math
import pathlib


TARGET_BATCH_COUNT = 9
MIN_BATCH_CHARS = 26_000
MAX_BATCH_CHARS = 300_000
MAX_BATCH_CHUNKS = 250
MAX_EXTRACTION_CONCURRENCY = 8

CONCEPT_TYPES = {
    "Technology", "Method", "Concept", "Organization", "Person", "Product",
    "Metric", "Risk", "Theme",
}
CLAIM_STATUSES = {"Observation", "Prediction", "Decision", "Question", "Tension"}
RELATION_TYPES = {
    "enables", "causes", "depends_on", "part_of", "refines", "competes_with",
    "contradicts", "relates_to",
}
TOP_LEVEL_FIELDS = {"concepts", "claims", "relations"}
CONCEPT_FIELDS = {"name", "type", "definition", "aliases", "chunk_ids"}
CLAIM_FIELDS = {"text", "status", "concepts", "chunk_id", "date"}
RELATION_FIELDS = {"source", "target", "type", "evidence_chunk_ids", "rationale"}


def adaptive_batch_char_budget(items):
    """Choose a bounded budget that targets about nine batches for large deltas."""
    total_chars = sum(len(item.get("text", "")) for item in items)
    budget = math.ceil(total_chars / TARGET_BATCH_COUNT) if total_chars else MIN_BATCH_CHARS
    return min(MAX_BATCH_CHARS, max(MIN_BATCH_CHARS, budget))


def batch_items(items):
    """Batch ordered extraction items by adaptive character and chunk limits."""
    items = list(items)
    oversized = [
        item.get("chunk_id", "<unknown>")
        for item in items
        if len(item.get("text", "")) > MAX_BATCH_CHARS
    ]
    if oversized:
        raise ValueError(
            "chunks exceed the maximum extraction batch size and must be split: "
            + ", ".join(oversized)
        )
    budget = adaptive_batch_char_budget(items)
    batches = []
    current = []
    current_chars = 0
    for item in items:
        text_chars = len(item.get("text", ""))
        if current and (
            current_chars + text_chars > budget or len(current) >= MAX_BATCH_CHUNKS
        ):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += text_chars
    if current:
        batches.append(current)
    guidance = {
        "strategy": "adaptive_char_budget",
        "target_batch_count": TARGET_BATCH_COUNT,
        "selected_batch_chars": budget,
        "min_batch_chars": MIN_BATCH_CHARS,
        "max_batch_chars": MAX_BATCH_CHARS,
        "max_chunks_per_batch": MAX_BATCH_CHUNKS,
        "total_chars": sum(len(item.get("text", "")) for item in items),
        "total_chunks": len(items),
    }
    return batches, guidance


def extraction_batch_id(chunk_ids):
    payload = "\n".join(chunk_ids).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def _check_fields(value, required, path, errors):
    if not isinstance(value, dict):
        errors.append(f"{path}: expected an object")
        return False
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        errors.append(f"{path}: missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{path}: unexpected fields: {', '.join(extra)}")
    return not missing


def _check_string(value, path, errors, allow_empty=False):
    if not isinstance(value, str):
        errors.append(f"{path}: expected a string")
        return False
    if not allow_empty and not value.strip():
        errors.append(f"{path}: must not be empty")
        return False
    return True


def _check_string_list(value, path, errors):
    if not isinstance(value, list):
        errors.append(f"{path}: expected an array of strings")
        return False
    valid = True
    for index, item in enumerate(value):
        if not _check_string(item, f"{path}[{index}]", errors):
            valid = False
    return valid


def validate_extraction_data(data, allowed_chunk_ids):
    """Return actionable schema and provenance errors for one extraction batch."""
    errors = []
    allowed_chunk_ids = set(allowed_chunk_ids)
    if not isinstance(data, dict):
        return ["top-level: expected a JSON object"]
    missing = sorted(TOP_LEVEL_FIELDS - set(data))
    extra = sorted(set(data) - TOP_LEVEL_FIELDS)
    if missing:
        errors.append(f"top-level: missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"top-level: unexpected fields: {', '.join(extra)}")

    sections = {}
    for field in sorted(TOP_LEVEL_FIELDS):
        value = data.get(field)
        if not isinstance(value, list):
            errors.append(f"{field}: expected an array")
            sections[field] = []
        else:
            sections[field] = value

    concept_names = set()
    for index, concept in enumerate(sections["concepts"]):
        path = f"concepts[{index}]"
        if not _check_fields(concept, CONCEPT_FIELDS, path, errors):
            continue
        if _check_string(concept["name"], f"{path}.name", errors):
            if concept["name"] in concept_names:
                errors.append(f"{path}.name: duplicate concept name {concept['name']!r}")
            concept_names.add(concept["name"])
        if _check_string(concept["type"], f"{path}.type", errors):
            if concept["type"] not in CONCEPT_TYPES:
                errors.append(
                    f"{path}.type: expected one of {', '.join(sorted(CONCEPT_TYPES))}"
                )
        _check_string(concept["definition"], f"{path}.definition", errors)
        _check_string_list(concept["aliases"], f"{path}.aliases", errors)
        if _check_string_list(concept["chunk_ids"], f"{path}.chunk_ids", errors):
            if not concept["chunk_ids"]:
                errors.append(f"{path}.chunk_ids: expected at least one batch chunk ID")
            unknown = sorted(set(concept["chunk_ids"]) - allowed_chunk_ids)
            if unknown:
                errors.append(
                    f"{path}.chunk_ids: IDs outside this batch: {', '.join(unknown)}"
                )

    for index, claim in enumerate(sections["claims"]):
        path = f"claims[{index}]"
        if not _check_fields(claim, CLAIM_FIELDS, path, errors):
            continue
        _check_string(claim["text"], f"{path}.text", errors)
        if _check_string(claim["status"], f"{path}.status", errors):
            if claim["status"] not in CLAIM_STATUSES:
                errors.append(
                    f"{path}.status: expected one of {', '.join(sorted(CLAIM_STATUSES))}"
                )
        if _check_string_list(claim["concepts"], f"{path}.concepts", errors):
            unknown = sorted(set(claim["concepts"]) - concept_names)
            if unknown:
                errors.append(
                    f"{path}.concepts: unknown concept references: {', '.join(unknown)}"
                )
        if _check_string(claim["chunk_id"], f"{path}.chunk_id", errors):
            if claim["chunk_id"] not in allowed_chunk_ids:
                errors.append(f"{path}.chunk_id: ID is outside this batch")
        if claim["date"] is not None and not isinstance(claim["date"], str):
            errors.append(f"{path}.date: expected a string or null")

    for index, relation in enumerate(sections["relations"]):
        path = f"relations[{index}]"
        if not _check_fields(relation, RELATION_FIELDS, path, errors):
            continue
        for endpoint in ("source", "target"):
            if _check_string(relation[endpoint], f"{path}.{endpoint}", errors):
                if relation[endpoint] not in concept_names:
                    errors.append(
                        f"{path}.{endpoint}: unknown concept reference "
                        f"{relation[endpoint]!r}"
                    )
        if _check_string(relation["type"], f"{path}.type", errors):
            if relation["type"] not in RELATION_TYPES:
                errors.append(
                    f"{path}.type: expected one of {', '.join(sorted(RELATION_TYPES))}"
                )
        if _check_string_list(
            relation["evidence_chunk_ids"], f"{path}.evidence_chunk_ids", errors
        ):
            if not relation["evidence_chunk_ids"]:
                errors.append(
                    f"{path}.evidence_chunk_ids: expected at least one batch chunk ID"
                )
            unknown = sorted(
                set(relation["evidence_chunk_ids"]) - allowed_chunk_ids
            )
            if unknown:
                errors.append(
                    f"{path}.evidence_chunk_ids: IDs outside this batch: "
                    f"{', '.join(unknown)}"
                )
        _check_string(relation["rationale"], f"{path}.rationale", errors)
    return errors


def load_extraction_output(path, allowed_chunk_ids):
    """Decode, parse, and validate an extraction output without modifying it."""
    path = pathlib.Path(path)
    if not path.exists():
        return None, ["output file does not exist"]
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [f"output is not valid UTF-8: {exc}"]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [
            f"output is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ]
    errors = validate_extraction_data(data, allowed_chunk_ids)
    return data, errors
