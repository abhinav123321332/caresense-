from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parent
expected = json.loads((root / "CHECKSUMS.sha256.json").read_text())
bad = [name for name, digest in expected.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
if bad: raise SystemExit("Checksum mismatch: " + ", ".join(bad))
print(f"Verified {len(expected)} distribution file checksums")
