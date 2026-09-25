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

### Optional subscription gateway

The separate private `sanpra_tally_server` app provides Tally Registration and subscription checks. Configure the Subscription Gateway fields in Tally Settings, then enable Use Subscription Gateway. Errors never fall back to direct Tally when enabled. Existing installations keep direct routing until configured. This stage does not hide the conversion source; moving conversion logic to the private server is still required before shipping an enforced subscription product.

Client tests: `env/bin/python -m unittest discover -s apps/sanpra_tally/sanpra_tally/tests -v`

### Private gateway configuration

The client no longer reads a Tally Settings document. Configure the per-client registration only in the server-managed site config; do not expose these values in Desk forms:

```bash
bench --site CLIENT_SITE set-config sanpra_tally_gateway '{"url":"https://subscriptions.example.com","registration":"REGISTRATION_ID","company":"ERP Company","erp_url":"https://client.example.com","api_key":"CLIENT_API_KEY","api_secret":"CLIENT_API_SECRET","tally_company":"Exact Tally Company"}'
bench --site CLIENT_SITE clear-cache
```

`sanpra_tally` reads this configuration at runtime. If `registration` or any credential is missing, no Tally request is sent. The private server remains the authority for status and expiry. Remove any old Tally Settings record after confirming the site config works; it is no longer used by the connector.

### Payment Entry sync

Submitted Payment Entries use the queued submit/cancel sync flow described below. Pay creates
Payment vouchers, Receive creates Receipt vouchers, and Internal Transfer creates
Contra vouchers in the company configured by the private gateway. Customer and
Supplier postings use their party ledgers; other postings use Account ledgers.
Voucher amounts come from the submitted, non-cancelled GL entries, including
charges, taxes and exchange differences. Unsupported party types fail with an
error log instead of being exported to a generic party account.

Successful creation stores the Tally voucher ID and posting date. Cancellation uses that saved identity and company. Synced ERP documents are retained for reconciliation.
A created voucher with a missing ID requires reconciliation in Tally before retry.
This follows the existing invoice integration's ledger-level posting; invoice-wise
bill settlement is not exported. Existing submitted entries are not bulk synced.

Payment regression tests are included in the client test command above. Site dry
runs mock Tally delivery and metadata writes; they do not confirm live Tally import.


### Sync Status, Check & Retry, and Ledger Mapping

SI, PI, JE and PE now show Tally Sync Status, Tally Sync Message and Last Tally
Attempt. Submit/cancel queues a long-worker job **after the ERP transaction commits**.
Use the document's **Tally → Check Tally** for a read-only remote check, or
**Tally → Check & Retry** to check and then sync an absent voucher. Users need
write permission on the document and an Accounts User, Accounts Manager or
System Manager role. Status refreshes while the document is open.

The worker locks each document and checks Server B's subscription-authorized
voucher lookup before creating anything. It compares company, date, voucher type,
number and saved ID/ERP remote identity. It records a delivery marker before the
external voucher write. A timeout, malformed response, missing ID or ambiguous
match becomes **Needs Review**; an uncertain delivery is never blindly resent,
even if a later lookup returns no match. Reconcile these entries in Tally first.
A cancelled ERP document can retry cancellation; check-only never cancels it.
Synced or uncertain ERP documents cannot be deleted, preserving reconciliation
history. No existing submitted documents are automatically bulk synced.

Open **Tally Ledger Mapping** (or **Tally → Ledger Mapping**) and select Company,
ERP Record Type (Account/Customer/Supplier), ERP Record and Tally Ledger Name.
Accounts Manager/System Manager can maintain mappings. Each company/record has
one mapping; disabled/missing mappings use the ERP account or party name.
Invoice income/expense/tax rows, JE and PE use these names. Each site still uses
its configured private gateway registration; mappings do not register additional
companies or redirect traffic to another Tally company. Do not rename a mapping
for already-synced history without reconciling that history in Tally.

Deploy the client changes on Server A and `sanpra_tally_server.lookup` on Server B,
run migrations on Server A, and restart web/workers. The lookup endpoint accepts
only a posting date and registration identity and constructs its own read-only
query. Arbitrary export XML remains forbidden at the gateway import endpoint.
Its XML structure follows [Tally's collection export documentation](https://help.tallysolutions.com/docs/td9rel54/integration-capabilities/case_study_1.htm).

Validation: client/server unit tests plus SI/PI/JE/PE dry runs with mocked network
and DB writes. On nutrichdev, a live read-only collection lookup succeeded. Actual
voucher imports with the new mapped ledgers still require business validation.
The separate server-side snapshot converters are not used by this client's XML
forwarding path; the new UI/mapping behavior applies to the active client path.
