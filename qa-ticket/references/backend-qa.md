# Backend QA

Read this file before backend route discovery or functional requests.

## Discover routes authoritatively

Resolve routes in this order:

1. reachable OpenAPI/Swagger specification;
2. source route definitions;
3. changed route code from the diff.

Never guess a route or prefer a user-proposed path over contradictory OpenAPI/source route evidence. Validate current project conventions rather than assuming `/openapi.json` exists.

## Execute and capture evidence

Use the discovered local URL and project test auth. Capture the response body separately from the terminal HTTP status for each request. A backend PASS requires the **status and expected response content** to match the plan. A 2xx with missing or wrong fields is FAIL.

Use the project's equivalent client when required; otherwise retain explicit method/payload capture with these compact curl patterns:

```bash
curl -s -w "\n%{http_code}" "<URL>"
curl -s -w "\n%{http_code}" -X POST "<URL>" -H "Content-Type: application/json" -d '<JSON>'
curl -s -w "\n%{http_code}" -X PATCH "<URL>/<ID>" -H "Content-Type: application/json" -d '<JSON>'
curl -s -w "\n%{http_code}" -X DELETE "<URL>/<ID>"
```

Treat the last output line as status and everything before it as body; retain both in the attempt evidence.

Use unique test data (for example a timestamp/UUID suffix) to prevent collisions. For create operations, capture the returned `id`/`_id` and reuse it. Preserve the planned CRUD sequence:

1. create and capture ID;
2. read and verify content;
3. update and verify changed content;
4. list and verify presence;
5. delete for cleanup;
6. verify delete with the expected not-found result.

Record method, URL, payload, status, and relevant response fields. For a valid nonexistent-resource test, use a syntactically valid ID that is absent. For permission tests, use a safe different test user rather than production credentials.

## Failure evidence

On mismatch, preserve expected versus actual status/body. Read server logs only when needed to diagnose. An unavailable service, missing data, ambiguous response, or failed cleanup is never PASS; classify it according to the retry/report protocol. Cleanup still runs where safe even when another lifecycle assertion fails.
