# Mintlify Documentation


### Get Started

Clone the repo

```
https://github.com/Xenovia-io/docs
```

### Development

Install the [Mintlify CLI](https://www.npmjs.com/package/mintlify) to preview the documentation changes locally. To install, use the following command

```
npm i -g mintlify  # install Node.js (version 19 or higher) before proceeding.
```

Run the following command at the root of your documentation (where docs.json is)

```
mintlify dev
```


#### Troubleshooting

- Mintlify dev isn't running - Run `mintlify install` it'll re-install dependencies.
- Page loads as a 404 - Make sure you are running in a folder with `docs.json`


Refer https://mintlify.com/docs for more details and components/

### Developing Documentation

Pages in your documentation should be organized using the `docs.json` configuration file. Here's how to structure your pages:

1. **Navigation Tabs**: Group your pages into tabs using the `navigation.tabs` field
```json
{
  "navigation": {
    "tabs": [
      {
        "tab": "Getting Started",
        "groups": [...]
      }
    ]
  }
}
```

2. **Page Groups**: Within each tab, create groups to organize related pages
```json
{
  "groups": [
    {
      "group": "Overview",
      "pages": ["introduction", "quickstart"]
    }
  ]
}
```

3. **Adding Pages**: List your pages in the `pages` array using the file path without the `.mdx` extension
```json
{
  "pages": ["introduction", "folder/page", "folder/another-page"]
}
```

4. **OpenAPI Integration**: For API documentation, you can automatically generate pages from an OpenAPI spec
```json
{
  "groups": [
    {
      "group": "Endpoints",
      "openapi": {
        "source": "/api-reference/openapi.yaml",
        "directory": "api-reference"
      }
    }
  ]
}
```



