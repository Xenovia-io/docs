# Xenovia Docs

Documentation source for Xenovia's runtime governance platform, built with Mintlify.

## Local development

### Prerequisites

- Node.js 19+ (Node.js 20+ recommended)
- npm

### Install Mintlify CLI

```bash
npm i -g mintlify
```

### Run locally

From the repo root (where `docs.json` exists):

```bash
mintlify dev
```

By default, Mintlify serves docs at `http://localhost:3000`.

## Repo structure

```text
.
├── introduction.mdx
├── getting-started/
│   ├── overview.mdx
│   └── quickstart.mdx
├── platform/
│   ├── overview.mdx
│   ├── runtime-architecture.mdx
│   ├── policies-and-approvals.mdx
│   ├── tools-and-access.mdx
│   └── traces-and-remediation.mdx
├── api-reference/
│   ├── introduction.mdx
│   ├── authentication.mdx
│   └── errors-and-limits.mdx
└── docs.json
```

## Editing guidelines

- Keep navigation in sync with `docs.json`.
- Keep page metadata (`title`, `description`, `icon`) consistent.
- Treat `api-reference/` as both authored API guides and generated endpoint docs from OpenAPI.

## Troubleshooting

- `mintlify dev` fails to start: run `mintlify install` and retry.
- Pages show `404`: verify page path is included in `docs.json`.
- OpenAPI pages missing: verify the `openapi.source` URL in `docs.json` is reachable.

## References

- [Mintlify docs](https://mintlify.com/docs)
- [Xenovia website](https://xenovia.io)
