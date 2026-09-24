### Sanpra Tally

Sanpra Tally Custom Application

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app sanpra_tally https://github.com/Sanprasoftware/tallyerp.git --branch main
bench install-app sanpra_tally
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/sanpra_tally
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

### App and method paths

- App/package: `sanpra_tally`
- Frappe module: `Sanpra Tally`
- Tally methods: `sanpra_tally.sanpra_tally.tally.<module>.<method>`
- AI endpoint: `sanpra_tally.sanpra_tally.ai.api.ask`
- Purchase summary API: `sanpra_tally.api.purchase_summary`
- Static assets: `/assets/sanpra_tally/`

Existing integrations calling `parshwa.*` must use the new paths. The Tally company name is independent of the app name.
