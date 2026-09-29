"""Subscription transport; locally shipped conversion source remains visible to clients."""
import hashlib
from ipaddress import IPv4Address
from urllib.parse import urlsplit
from uuid import uuid4

import requests
import frappe


def failure(message):
    return {"success": False, "response": message}



def post_to_registered_tally(result, xml_data):
    try:
        expected_hash = result.get("payload_hash")
        if expected_hash and expected_hash != hashlib.sha256(xml_data.encode()).hexdigest():
            return failure("Subscription server returned a mismatched Tally payload.")
        ip = str(IPv4Address(str(result.get("tally_ipv4") or "")))
        port = int(result.get("tally_port"))
        if not 1 <= port <= 65535:
            return failure("Registered Tally port is invalid.")
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
                f"http://{ip}:{port}", data=xml_data.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=(5, 30), allow_redirects=False,
            )
        return {"success": response.status_code == 200, "status_code": response.status_code,
                "response": response.text}
    except (requests.RequestException, ValueError, TypeError):
        return failure("Local Tally delivery could not be confirmed. Check Tally before retrying.")


class GatewaySettings(dict):
    def __getattr__(self, name):
        return self.get(name)

    def get_password(self, fieldname, raise_exception=False):
        return self.get(fieldname)


def _settings_from_doctype():
    try:
        if not frappe.db.exists("DocType", "Sanpra Tally Gateway Settings"):
            return None
        settings = frappe.get_single("Sanpra Tally Gateway Settings")
    except Exception:
        return None
    if not settings.get("enabled"):
        return None
    return {
        "url": settings.get("gateway_url"),
        "registration": settings.get("registration"),
        "company": settings.get("company"),
        "erp_url": settings.get("erp_site_url"),
        "api_key": settings.get("api_key"),
        "api_secret": settings.get_password("api_secret", raise_exception=False),
        "tally_company": settings.get("tally_company"),
    }


def _settings_from_site_config(company=None):
    company_gateways = frappe.conf.get("sanpra_tally_gateways")
    if company and company_gateways is not None:
        if not isinstance(company_gateways, dict):
            raise ValueError("Company-wise Tally gateway configuration must be a mapping.")
        raw = company_gateways.get(company)
        if not isinstance(raw, dict):
            raise ValueError(f"No Tally registration is configured for ERP company {company}.")
        return raw
    return frappe.conf.get("sanpra_tally_gateway") or {}


def get_settings(doc=None):
    company = doc.get("company") if doc is not None else None
    raw = _settings_from_doctype() or _settings_from_site_config(company)
    if not isinstance(raw, dict):
        raise ValueError("Private subscription gateway configuration is missing.")
    values = {"gateway_url": raw.get("url"), "gateway_registration": raw.get("registration"),
        "gateway_company": raw.get("company"), "gateway_erp_url": raw.get("erp_url"),
        "gateway_api_key": raw.get("api_key"), "gateway_api_secret": raw.get("api_secret"),
        "tally_company": raw.get("tally_company") or raw.get("company"), "enabled": 1}
    if company and values["gateway_company"] != company:
        raise ValueError("This ERP company is not registered on the private server.")
    if not values["gateway_registration"]:
        raise ValueError("This ERP site has no subscription registration.")
    return GatewaySettings(values)


def send_via_gateway(settings, xml_data):
    gateway = str(settings.get("gateway_url") or "").rstrip("/")
    parsed = urlsplit(gateway)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return failure("Configure the subscription server HTTP or HTTPS URL without a path.")
    api_key = settings.get("gateway_api_key")
    api_secret = settings.get_password("gateway_api_secret", raise_exception=False)
    if not all((api_key, api_secret, settings.get("gateway_registration"),
                settings.get("gateway_erp_url"), settings.get("gateway_company"))):
        return failure("Subscription credentials, registration, ERP URL and company are required.")
    request_id = uuid4().hex
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
            f"{gateway}/api/method/sanpra_tally_server.api.forward",
            headers={"Authorization": f"token {api_key}:{api_secret}"},
            json={"registration": settings.gateway_registration,
                  "erp_site_url": settings.gateway_erp_url, "company_name": settings.gateway_company,
                  "request_id": request_id, "xml_data": xml_data},
            timeout=(5, 45), allow_redirects=False,
        )
        if response.status_code != 200:
            return failure(f"Subscription request denied or failed (HTTP {response.status_code}).")
        body = response.json()
        result = body.get("message") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            return failure("Invalid subscription server response.")
        if result.get("success") is not True:
            return failure(result.get("response", "Subscription request was denied."))
        if result.get("connection_mode") == "Client Connector":
            if result.get("request_id") != request_id:
                return failure("Subscription server returned a mismatched request ID.")
            return post_to_registered_tally(result, xml_data)
        if not isinstance(result.get("response"), str):
            return failure("Subscription server did not return a Tally response.")
        return result
    except (requests.RequestException, ValueError, TypeError):
        return failure("Gateway/Tally delivery could not be confirmed. Check Tally before retrying.")


def lookup_vouchers(settings, posting_date):
    """Ask Server B for its fixed read-only query, then use the registered route."""
    gateway = str(settings.get('gateway_url') or '').rstrip('/')
    parsed = urlsplit(gateway)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return failure('Invalid subscription server URL.')
    if not all(settings.get(k) for k in ('gateway_api_key','gateway_api_secret','gateway_registration',
                                        'gateway_erp_url','gateway_company')):
        return failure('Subscription configuration is incomplete.')
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(gateway + '/api/method/sanpra_tally_server.lookup.voucher_lookup',
            headers={'Authorization': f'token {settings.gateway_api_key}:{settings.gateway_api_secret}'},
            json={'registration': settings.gateway_registration,'erp_site_url':settings.gateway_erp_url,
                  'company_name':settings.gateway_company,'posting_date':str(posting_date)[:10]},
            timeout=(5,45),allow_redirects=False)
        if response.status_code != 200:
            return failure(f'Tally check failed (HTTP {response.status_code}). Verify Server B is updated and the subscription is active.')
        result = response.json().get('message')
        if not isinstance(result,dict):
            return failure('Tally check was not authorized or did not complete.')
        if result.get('success') is not True:
            return failure(result.get('response') or 'Tally check was not authorized or did not complete.')
        if result.get('connection_mode') == 'Client Connector':
            xml = result.get('xml')
            if not isinstance(xml, str) or not xml.strip():
                return failure('Subscription server did not return a Tally lookup request.')
            return post_to_registered_tally(result, xml)
        return result
    except requests.RequestException as exc:
        return failure(f'Tally check request failed: {exc}; no voucher was sent.')
    except Exception:
        return failure('Tally check could not be completed; no voucher was sent.')



def gateway_headers(settings):
    return {"Authorization": f"token {settings.gateway_api_key}:{settings.get_password('gateway_api_secret', raise_exception=False)}"}


def post_gateway_method(settings, method, payload, timeout=(5, 120)):
    gateway = str(settings.get("gateway_url") or "").rstrip("/")
    parsed = urlsplit(gateway)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return failure("Configure the subscription server HTTP or HTTPS URL without a path.")
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
                f"{gateway}/api/method/{method}",
                headers=gateway_headers(settings), json=payload,
                timeout=timeout, allow_redirects=False,
            )
        if response.status_code != 200:
            return failure(f"Subscription request denied or failed (HTTP {response.status_code}).")
        body = response.json()
        result = body.get("message") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            return failure("Invalid subscription server response.")
        return result
    except (requests.RequestException, ValueError, TypeError):
        return failure("Subscription server request could not be completed.")


def run_conversion_job(settings, action, snapshot, request_id):
    base = {"registration": settings.gateway_registration, "erp_site_url": settings.gateway_erp_url,
            "company_name": settings.gateway_company}
    result = post_gateway_method(settings, "sanpra_tally_server.conversion_api.begin",
        {**base, "request_id": request_id, "action": action, "snapshot": snapshot})
    for _ in range(200):
        if result.get("state") == "complete":
            return result
        if result.get("state") == "continue" and result.get("job"):
            result = post_gateway_method(settings, "sanpra_tally_server.conversion_api.continue_job",
                {**base, "job_id": result["job"]})
            continue
        if result.get("xml") and result.get("job") and result.get("step") is not None:
            tally_result = post_to_registered_tally(result, result["xml"])
            result = post_gateway_method(settings, "sanpra_tally_server.conversion_api.acknowledge",
                {**base, "job_id": result["job"], "step": result["step"], "result": tally_result})
            continue
        return failure(result.get("response") or "Private conversion server returned an incomplete job.")
    return failure("Private conversion job exceeded the step limit.")
