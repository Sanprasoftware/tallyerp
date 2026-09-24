
import frappe
import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"


def get_erp_data(question):
    q = question.lower()

    if "customer" in q and ("how many" in q or "count" in q or "total" in q):
        count = frappe.db.count("Customer")
        return f"There are {count} Customers."

    if "supplier" in q and ("how many" in q or "count" in q or "total" in q):
        count = frappe.db.count("Supplier")
        return f"There are {count} Suppliers."

    if "item" in q and ("how many" in q or "count" in q or "total" in q):
        count = frappe.db.count("Item")
        return f"There are {count} Items."

    if "sales invoice" in q and ("how many" in q or "count" in q):
        count = frappe.db.count("Sales Invoice")
        return f"There are {count} Sales Invoices."

    if "purchase invoice" in q and ("how many" in q or "count" in q):
        count = frappe.db.count("Purchase Invoice")
        return f"There are {count} Purchase Invoices."

    if "sales" in q and ("total" in q or "amount" in q):
        total = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabSales Invoice`
            WHERE docstatus = 1
        """)[0][0]

        return f"The total sales amount is {total}."

    if "purchase" in q and ("total" in q or "amount" in q):
        total = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1
        """)[0][0]

        return f"The total purchase amount is {total}."

    return None


def call_ollama(question):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": question,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result.get("response", "").strip()

    except Exception as e:
        frappe.log_error(
            title="Sanpra Tally AI - Ollama Error",
            message=str(e)
        )
        return None


@frappe.whitelist()
def ask(question):
    question = (question or "").strip()

    if not question:
        return {
            "success": False,
            "error": "Please enter a question."
        }

    # First try direct ERPNext database lookup.
    # This avoids using Ollama for simple questions.
    direct_answer = get_erp_data(question)

    if direct_answer:
        return {
            "success": True,
            "question": question,
            "answer": direct_answer,
            "source": "ERPNext"
        }

    # Only use Ollama when direct ERP handling is not enough.
    answer = call_ollama(question)

    if answer:
        return {
            "success": True,
            "question": question,
            "answer": answer,
            "source": "Ollama"
        }

    return {
        "success": False,
        "question": question,
        "error": "Local AI service is not available. Please make sure Ollama is running."
    }
