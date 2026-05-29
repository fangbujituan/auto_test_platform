"""Verify both CMD and bash cURL formats work."""
import sys
sys.path.insert(0, '.')
from app.routes.api_import import parse_curl

# bash 格式
bash_curl = (
    'curl "https://api.example.com/users?page=1" '
    '-H "accept: application/json" '
    '-H "authorization: Bearer token123" '
    '-H "content-type: application/json" '
    '--data-raw \'{"name":"test","age":25}\''
)

# CMD 格式
cmd_curl = (
    'curl ^"https://api.example.com/users?page=1^" '
    '^-H ^"accept: application/json^" '
    '^-H ^"authorization: Bearer token123^" '
    '^-H ^"content-type: application/json^" '
    '^--data-raw ^"^{^\\"name^\\":^\\"test\\",^\\"age^\\":25^}^"'
)

for label, curl in [("BASH", bash_curl), ("CMD", cmd_curl)]:
    print(f"=== {label} ===")
    p = parse_curl(curl)
    print(f"  method:   {p['method']}")
    print(f"  url:      {p['url']}")
    print(f"  base_url: {p['base_url']}")
    print(f"  path:     {p['path']}")
    print(f"  headers:  {len(p['headers'])} items")
    print(f"  params:   {p['params']}")
    print(f"  body:     {p['body']}")
    print(f"  bodytype: {p['body_type']}")
    print()
