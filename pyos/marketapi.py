"""The marketplace API version: what lets the marketplace change without breaking PythonOS systems that are already out there.

Three things carry a version:
  * the PythonOS (the client)   speaks API version CURRENT and still runs packages written for any version from OLDEST up to CURRENT
  * every package               declares the API it was written for: "api" in its data.json (missing = 1)
  * the catalog                 is published once per version: index-api<N>.json lists the packages written for API N or older, in the
                                format of API N. index.json is the API 1 catalog and is never changed in an incompatible way, so the
                                oldest PythonOS systems keep working. A client asks for the file of its own version first and falls
                                back to index.json (an older catalog server that does not have the versioned files yet).

Changing the marketplace (the plan):
  1. a change old systems could not cope with (a new data.json field they must honour, another permission model, a new catalog layout):
     raise CURRENT here, and write an adapter in ADAPTERS so packages of the earlier version still run under the new rules
  2. build_index.py then publishes index-api<CURRENT>.json as well; index.json and the older files stay as they are
  3. packages that need the new behaviour say "api": <CURRENT> and are only listed to systems that understand it
  4. much later, raise OLDEST to stop supporting the oldest packages (they are hidden and refused with a clear message)
This file is also loaded by tools/build_index.py, so it must only use the standard library.
"""
CURRENT = 1                          # the API version this PythonOS speaks
OLDEST = 1                           # the oldest package API it still runs

# ADAPTERS[n](meta) turns the manifest (data.json) of an API n package into one that API n+1 rules understand. Nothing to adapt yet.
ADAPTERS = {}


def package_api(meta):
    """The API version a package (its data.json, or its catalog entry) was written for."""
    try:
        value = int((meta or {}).get("api", 1))
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


def compatibility(meta):
    """(True, "") when this PythonOS can run the package, else (False, the reason in words)."""
    api = package_api(meta)
    if api > CURRENT:
        return False, (f"it needs a newer PythonOS (it uses marketplace API {api}; this system speaks API {CURRENT}). "
                       "Update PythonOS with: updatecheck")
    if api < OLDEST:
        return False, f"it is too old for this PythonOS (API {api}; the oldest still supported is API {OLDEST}); look for a newer version of the app"
    return True, ""


def index_names(current=None):
    """The catalog files to try, best first."""
    return [f"index-api{current or CURRENT}.json", "index.json"]


def index_api(index):
    """The API version a catalog was written for (a catalog without one is API 1)."""
    return package_api(index)


def adapt(meta):
    """The package's manifest as the current rules expect it (older ones are upgraded step by step; the original is not changed)."""
    meta = dict(meta or {})
    for version in range(package_api(meta), CURRENT):
        step = ADAPTERS.get(version)
        if step:
            meta = step(meta)
    return meta


def usable(packages):
    """(the packages this system can run, how many were left out)."""
    ok = [p for p in packages if compatibility(p)[0]]
    return ok, len(packages) - len(ok)
