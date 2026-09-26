"""Subscription transport; locally shipped conversion source remains visible to clients."""
import hashlib
from ipaddress import IPv4Address
from urllib.parse import urlsplit
from uuid import uuid4

import requests
import frappe


def failure(message):
    return {"success": False, "response": message}



class GatewaySettings(dict):
    def __getattr__(self, name):
        return self.get(name)
    def get_password(self, fieldname, raise_exception=False):
        return self.get(fieldname)

def get_settings(doc=None):
    # Keep the legacy single-company setting as a fallback for background tasks
    # that do not carry an ERP document. Document syncs can select a registration
    # per ERP company using sanpra_tally_gateways.
    raw = None
    company = doc.get("company") if doc is not None else None
    company_gateways = frappe.conf.get("sanpra_tally_gateways")
    if company and company_gateways is not None:
        if not isinstance(company_gateways, dict):
            raise ValueError("Company-wise Tally gateway configuration must be a mapping.")
        raw = company_gateways.get(company)
        if not isinstance(raw, dict):
            raise ValueError(f"No Tally registration is configured for ERP company {company}.")
    else:
        raw = frappe.conf.get("sanpra_tally_gateway") or {}
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
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return failure("Configure the subscription server HTTPS URL without a path.")
    api_key = settings.get("gateway_api_key")
    api_secret = settings.get_password("gateway_api_secret", raise_exception=False)
    if not all((api_key, api_secret, settings.get("gateway_registration"),
                settings.get("gateway_erp_url"), settings.get("gateway_company"))):
        return failure("Subscription credentials, registration, ERP URL and company are required.")
    request_id = uuid4().hex
    try:
        response = requests.post(
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
        if result.get("connection_mode") != "Client Connector":
            if not isinstance(result.get("response"), str):
                return failure("Subscription server did not return a Tally response.")
            return result
        expected = hashlib.sha256(xml_data.encode("utf-8")).hexdigest()
        if (result.get("authorized") is not True or result.get("request_id") != request_id
                or result.get("payload_hash") != expected):
            return failure("Invalid subscription approval.")
        ip = IPv4Address(str(result.get("tally_ipv4", "")))
        port = int(result.get("tally_port", 0))
        if (ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or not 1 <= port <= 65535):
            return failure("Invalid registered Tally destination.")
        with requests.Session() as session:
            session.trust_env = False
            tally = session.post(f"http://{ip}:{port}", data=xml_data.encode("utf-8"),
                                 headers={"Content-Type": "text/xml; charset=utf-8"},
                                 timeout=(5, 30), allow_redirects=False)
        tally_success = tally.status_code == 200
        tally_text = tally.text or ""
        if "<EXCEPTIONS>" in tally_text and "<EXCEPTIONS>0</EXCEPTIONS>" not in tally_text:
            tally_success = False
        if "<LINEERROR>" in tally_text:
            tally_success = False
        return {"success": tally_success, "status_code": tally.status_code,
                "response": tally_text}
    except (requests.RequestException, ValueError, TypeError):
        return failure("Gateway/Tally delivery could not be confirmed. Check Tally before retrying.")


def lookup_vouchers(settings, posting_date):
    """Ask Server B for its fixed read-only query, then use the registered route."""
    gateway = str(settings.get('gateway_url') or '').rstrip('/')
    parsed = urlsplit(gateway)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return failure('Invalid subscription server URL.')
    if not all(settings.get(k) for k in ('gateway_api_key','gateway_api_secret','gateway_registration',
                                        'gateway_erp_url','gateway_company')):
        return failure('Subscription configuration is incomplete.')
    try:
        response = requests.post(gateway + '/api/method/sanpra_tally_server.lookup.voucher_lookup',
            headers={'Authorization': f'token {settings.gateway_api_key}:{settings.gateway_api_secret}'},
            json={'registration': settings.gateway_registration,'erp_site_url':settings.gateway_erp_url,
                  'company_name':settings.gateway_company,'posting_date':str(posting_date)[:10]},
            timeout=(5,45),allow_redirects=False)
        if response.status_code != 200:
            return failure(f'Tally check failed (HTTP {response.status_code}). Verify Server B is updated and the subscription is active.')
        result = response.json().get('message')
        if not isinstance(result,dict) or result.get('success') is not True:
            return failure('Tally check was not authorized or did not complete.')
        if result.get('connection_mode') != 'Client Connector':
            return result
        xml = result.get('xml','')
        if result.get('authorized') is not True or hashlib.sha256(xml.encode()).hexdigest() != result.get('payload_hash'):
            return failure('Invalid Tally lookup authorization.')
        # Only the server-generated read-only export is accepted here.
        from defusedxml.ElementTree import fromstring
        root = fromstring(xml,forbid_dtd=True)
        if (root.findtext('./HEADER/TALLYREQUEST') != 'Export'
                or root.findtext('./HEADER/ID') != 'SanpraVoucherLookup'
                or root.findtext('.//SVCURRENTCOMPANY') != settings.tally_company):
            return failure('Invalid Tally lookup query.')
        ip = IPv4Address(str(result.get('tally_ipv4','')))
        port = int(result.get('tally_port',0))
        if (ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or not 1 <= port <= 65535):
            return failure('Invalid registered Tally destination.')
        with requests.Session() as session:
            session.trust_env = False
            tally = session.post(f'http://{ip}:{port}',data=xml.encode(),
                headers={'Content-Type':'text/xml; charset=utf-8'},timeout=(5,30),allow_redirects=False)
        return {'success':tally.status_code == 200,'response':tally.text or ''}
    except Exception:
        return failure('Tally check could not be completed; no voucher was sent.')
