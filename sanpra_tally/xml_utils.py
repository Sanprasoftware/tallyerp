"""Shared strict response parsing for the active ERP connector."""
from defusedxml.ElementTree import fromstring


def parse_response(text):
    root = fromstring(text or '', forbid_dtd=True, forbid_entities=True, forbid_external=True)
    if any((n.text or '').strip() for n in root.iter('LINEERROR')):
        raise ValueError('Tally rejected the request: ' + ' '.join(n.text or '' for n in root.iter('LINEERROR')))
    if any(int(n.text or 0) for tag in ('ERRORS', 'EXCEPTIONS') for n in root.iter(tag)):
        raise ValueError('Tally reported errors or exceptions.')
    if any((n.text or '').strip() == '0' for n in root.iter('STATUS')):
        raise ValueError('Tally reported a failed request.')
    return root


def checked_result(result, counter=None):
    if not result.get('success'):
        return result
    try:
        root = parse_response(result.get('response'))
        if counter and int(root.findtext('.//' + counter, '0')) != 1:
            raise ValueError('Tally did not confirm the requested voucher operation.')
    except Exception as exc:
        return {**result, 'success': False, 'response': str(exc), 'uncertain': True}
    return result
