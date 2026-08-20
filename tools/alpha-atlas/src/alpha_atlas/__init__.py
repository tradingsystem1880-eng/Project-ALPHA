"""Project Alpha Atlas: read-only knowledge graph and explanation layer.

Atlas reads the repository as text/AST/JSON and never imports alpha_* packages.
`core` and `generators` are deliberately stdlib-only so the root test suite can
import them without the Atlas virtualenv.
"""
