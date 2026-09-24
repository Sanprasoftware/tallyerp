import requests
import frappe


def get_tally_settings():
    settings_name = frappe.db.get_value(
        "Tally Settings",
        {"enabled": 1},
        "name"
    )

    if not settings_name:
        frappe.throw("Tally Settings not configured or disabled.")

    settings = frappe.get_doc(
        "Tally Settings",
        settings_name
    )

    if not settings.tally_host:
        frappe.throw("Tally Host is not configured.")

    return settings


def send_to_tally(xml_data):
    # your existing code here
    settings = get_tally_settings()

    host = settings.tally_host
    port = settings.tally_port or 9000

    url = f"http://{host}:{port}"

    try:
        response = requests.post(
            url,
            data=xml_data.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8"
            },
            timeout=5
        )

        if response.status_code != 200:
            frappe.log_error(
                title="Tally HTTP Error",
                message=(
                    f"URL: {url}\n"
                    f"HTTP Status: {response.status_code}\n\n"
                    f"Response:\n{response.text}"
                )
            )

            return {
                "success": False,
                "status_code": response.status_code,
                "response": response.text
            }

        return {
            "success": True,
            "status_code": response.status_code,
            "response": response.text
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "response": f"Cannot connect to Tally at {url}"
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "response": "Tally connection timed out"
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Tally Integration Error"
        )

        return {
            "success": False,
            "response": str(e)
        }