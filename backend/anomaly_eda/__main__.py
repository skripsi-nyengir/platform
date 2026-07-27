import json

from . import toolchain_versions


print(json.dumps(toolchain_versions(), sort_keys=True))
