"""Print a k8s Secret manifest built from an env file (to be piped straight into sops)."""

import json
import sys

REQUIRED = ("TG_API_ID", "TG_API_HASH", "TG_SESSION", "MCP_PATH_SECRET")

values = {}
for line in open(sys.argv[1]).read().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

missing = [k for k in REQUIRED if not values.get(k)]
if missing:
    sys.exit(f"{sys.argv[1]}: не хватает {', '.join(missing)}")

print("apiVersion: v1\nkind: Secret\nmetadata:\n  name: app-secrets\ntype: Opaque\nstringData:")
for key in REQUIRED:
    print(f"  {key}: {json.dumps(values[key])}")
