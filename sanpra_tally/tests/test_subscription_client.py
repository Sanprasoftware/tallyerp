import unittest
from unittest.mock import MagicMock, patch
import requests
from sanpra_tally.subscription_client import send_via_gateway

XML = '<ENVELOPE><HEADER><TALLYREQUEST>Import</TALLYREQUEST></HEADER><BODY><SVCURRENTCOMPANY>Demo</SVCURRENTCOMPANY></BODY></ENVELOPE>'

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.settings = MagicMock()
        values = dict(gateway_url='https://subscriptions.example.com', gateway_api_key='key',
                      gateway_registration='reg', gateway_erp_url='https://erp.example.com', gateway_company='Demo')
        self.settings.get.side_effect = values.get
        self.settings.get_password.return_value = 'secret'
        for k, v in values.items():
            setattr(self.settings, k, v)

    @patch('sanpra_tally.subscription_client.requests.Session')
    @patch('sanpra_tally.subscription_client.requests.post')
    def test_denial_never_reaches_tally(self, post, session):
        post.return_value.status_code = 403
        self.assertFalse(send_via_gateway(self.settings, XML)['success'])
        session.assert_not_called()

    @patch('sanpra_tally.subscription_client.requests.Session')
    @patch('sanpra_tally.subscription_client.requests.post')
    def test_timeout_never_falls_back(self, post, session):
        post.side_effect = requests.Timeout()
        self.assertFalse(send_via_gateway(self.settings, XML)['success'])
        session.assert_not_called()

    @patch('sanpra_tally.subscription_client.requests.Session')
    @patch('sanpra_tally.subscription_client.requests.post')
    def test_bad_approval_never_reaches_tally(self, post, session):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'message': {'success': True, 'connection_mode': 'Client Connector', 'authorized': True, 'request_id': 'wrong', 'payload_hash': 'wrong'}}
        self.assertFalse(send_via_gateway(self.settings, XML)['success'])
        session.assert_not_called()

    @patch('sanpra_tally.subscription_client.requests.Session')
    @patch('sanpra_tally.subscription_client.requests.post')
    def test_vpn_result_has_no_second_delivery(self, post, session):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'message': {'success': True, 'response': '<CREATED>1</CREATED>'}}
        self.assertTrue(send_via_gateway(self.settings, XML)['success'])
        session.assert_not_called()

    @patch('sanpra_tally.subscription_client.requests.Session')
    @patch('sanpra_tally.subscription_client.requests.post')
    def test_valid_connector_approval_delivers_once(self, post, session):
        import hashlib
        def approve(*args, **kwargs):
            req = kwargs['json']
            response = MagicMock(status_code=200)
            response.json.return_value = {'message': {'success': True, 'authorized': True,
                'connection_mode': 'Client Connector', 'request_id': req['request_id'],
                'payload_hash': hashlib.sha256(XML.encode()).hexdigest(),
                'tally_ipv4': '192.168.1.10', 'tally_port': 9000}}
            return response
        post.side_effect = approve
        tally = session.return_value.__enter__.return_value.post
        tally.return_value.status_code = 200
        tally.return_value.text = '<CREATED>1</CREATED>'
        self.assertTrue(send_via_gateway(self.settings, XML)['success'])
        tally.assert_called_once()
        self.assertEqual(tally.call_args.args[0], 'http://192.168.1.10:9000')






class TransportRoutingTests(unittest.TestCase):
    @patch('sanpra_tally.sanpra_tally.tally_client.send_via_gateway')
    @patch('sanpra_tally.subscription_client.requests.post')
    @patch('sanpra_tally.sanpra_tally.tally_client.get_tally_settings')
    def test_enabled_gateway_failure_has_no_direct_fallback(self, settings, direct, gateway):
        from sanpra_tally.sanpra_tally.tally_client import send_to_tally
        settings.return_value.tally_company = "Demo"
        gateway.return_value = {'success': False, 'response': 'Expired'}
        self.assertFalse(send_to_tally(XML)['success'])
        gateway.assert_called_once()
        self.assertIs(gateway.call_args.args[0], settings.return_value)
        direct.assert_not_called()

    @patch('sanpra_tally.subscription_client.requests.post')
    def test_missing_credentials_do_not_send_anything(self, post):
        settings = MagicMock()
        settings.get.side_effect = {'gateway_url': 'https://subscriptions.example.com'}.get
        settings.get_password.return_value = None
        self.assertFalse(send_via_gateway(settings, XML)['success'])
        post.assert_not_called()
