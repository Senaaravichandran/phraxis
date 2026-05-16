import sys
from pathlib import Path
sys.path.insert(0, str(Path().absolute()))
from services.cloudant_service import CloudantService
import json

svc = CloudantService()
result = svc.client.post_find(db=svc.db_name, selector={"type": {"$eq": "intent"}}, limit=100).get_result()
docs = result.get('docs', [])
docs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
if docs:
    for k, v in docs[0].items():
        print(f'{k}: {v}')
