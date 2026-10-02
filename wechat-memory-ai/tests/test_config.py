import os
from pathlib import Path
import tempfile
import unittest

from wechat_memory.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'config.toml'
        self.base = (Path(__file__).parents[1] / 'config.example.toml').read_text('utf-8')

    def load(self, text=None, env=None):
        self.path.write_text(text or self.base, 'utf-8')
        return load_config(self.path, environ={} if env is None else env)

    def test_default_is_offline_and_paths_relative_to_config(self):
        c = self.load()
        self.assertTrue(c.dry_run)
        self.assertFalse(c.real_send)
        self.assertEqual(c.adapter, 'mock')
        self.assertEqual(c.model.provider, 'fake')
        self.assertEqual(c.data_dir, self.path.parent / 'data')

    def test_real_send_and_unsupported_adapters_fail_closed(self):
        for old, new in [('real_send = false', 'real_send = true'),
                         ('adapter = "mock"', 'adapter = "wechat"'),
                         ('proactive = false', 'proactive = true')]:
            with self.subTest(new=new), self.assertRaises(ConfigError):
                self.load(self.base.replace(old, new))

    def test_missing_peer_unknown_fields_wrong_types_and_nonfinite_fail(self):
        for text in [self.base.replace('peer_id = "mock:owner"', 'peer_id = ""'),
                     self.base + '\nunknown = 1\n',
                     self.base.replace('dry_run = true', 'dry_run = "false"'),
                     self.base.replace('daily_calls = 50', 'daily_calls = true'),
                     self.base.replace('daily_estimate = 2.0', 'daily_estimate = nan'),
                     self.base.replace('max_concurrency = 1', 'max_concurrency = 2'),
                     self.base.replace('context_chars = 6000', 'context_chars = 100')]:
            with self.subTest(text=text[-80:]), self.assertRaises(ConfigError):
                self.load(text)

    def network_config(self):
        return self.base.replace('provider = "fake"', 'provider = "chat_completions"').replace(
            'endpoint = ""', 'endpoint = "https://api.example.invalid/v1/chat/completions"').replace(
            'name = ""', 'name = "configured-model"')

    def test_network_requires_explicit_opt_in_and_credential(self):
        with self.assertRaises(ConfigError):
            self.load(self.network_config(), {'WECHAT_AI_API_KEY': 'test-secret'})
        with self.assertRaises(ConfigError):
            self.load(self.network_config().replace('allow_network = false', 'allow_network = true'))

    def test_credential_is_local_and_not_in_repr(self):
        secret = 'unit-test-secret-not-a-real-key'
        c = self.load(self.network_config().replace('allow_network = false', 'allow_network = true'),
                      {'WECHAT_AI_API_KEY': secret})
        self.assertEqual(c.model.api_key, secret)
        self.assertNotIn(secret, repr(c))
        (self.path.parent / '.env').write_text('WECHAT_AI_API_KEY=' + secret, 'utf-8')
        c = self.load(self.network_config().replace('allow_network = false', 'allow_network = true'))
        self.assertEqual(c.model.api_key, secret)

    def test_plain_http_remote_url_userinfo_and_query_rejected(self):
        base = self.network_config().replace('allow_network = false', 'allow_network = true')
        for url in ['http://example.invalid/v1/chat/completions',
                    'https://secret@host.invalid/v1/chat/completions',
                    'https://host.invalid/v1/chat/completions?api_key=bad']:
            with self.subTest(url=url), self.assertRaises(ConfigError):
                self.load(base.replace('https://api.example.invalid/v1/chat/completions', url),
                          {'WECHAT_AI_API_KEY': 'test-only'})

    def deepseek_config(self):
        return self.network_config().replace('provider = "chat_completions"', 'provider = "deepseek"').replace(
            'https://api.example.invalid/v1/chat/completions', 'https://api.deepseek.com/chat/completions').replace(
            'name = "configured-model"', 'name = "deepseek-flash"')

    def test_deepseek_requires_opt_in_and_local_credential(self):
        for text, env in ((self.deepseek_config(), {'WECHAT_AI_API_KEY':'TEST_ONLY'}),
                          (self.deepseek_config().replace('allow_network = false', 'allow_network = true'), {})):
            with self.assertRaisesRegex(ConfigError, 'network model requires opt-in'):
                self.load(text, env)

    def test_deepseek_accepts_only_the_two_explicit_official_endpoints(self):
        base = self.deepseek_config().replace('allow_network = false', 'allow_network = true')
        for endpoint in ('https://api.deepseek.com/chat/completions',
                         'https://api.deepseek.com/v1/chat/completions'):
            try:
                c = self.load(base.replace('https://api.deepseek.com/chat/completions', endpoint),
                              {'WECHAT_AI_API_KEY':'TEST_ONLY'})
            except ConfigError:
                self.fail('The DeepSeek profile does not accept its official endpoint')
            self.assertEqual(c.model.provider, 'deepseek')
            self.assertEqual(c.model.endpoint, endpoint)
            self.assertFalse(c.real_send)
            self.assertEqual(c.adapter, 'mock')
        for endpoint in ('https://api.example.invalid/chat/completions',
                         'http://api.deepseek.com/chat/completions',
                         'http://127.0.0.1/chat/completions',
                         'https://api.deepseek.com:444/chat/completions',
                         'https://api.deepseek.com/chat/completions?key=PRIVATE',
                         'https://api.deepseek.com/chat/completions#PRIVATE',
                         'https://PRIVATE@api.deepseek.com/chat/completions',
                         'https://api.deepseek.com/other/chat/completions',
                         'https://api.deepseek.com/chat/completions/',
                         'https://api.deepseek.com:443/chat/completions'):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ConfigError) as error:
                    self.load(base.replace('https://api.deepseek.com/chat/completions', endpoint),
                              {'WECHAT_AI_API_KEY':'TEST_ONLY'})
                self.assertNotIn('PRIVATE', str(error.exception))

    def test_deepseek_draft_remains_offline_until_both_switches_and_a_key_are_provided(self):
        template = Path(__file__).parents[1] / 'config.deepseek.example.toml'
        self.assertTrue(template.is_file(), 'The inactive DeepSeek configuration draft is missing')
        text = template.read_text('utf-8')
        c = self.load(text)
        self.assertEqual(c.model.provider, 'fake')
        self.assertFalse(c.model.allow_network)
        self.assertEqual(c.model.name, 'deepseek-flash')
        self.assertEqual(c.model.endpoint, 'https://api.deepseek.com/chat/completions')
        self.assertTrue(c.dry_run)
        self.assertFalse(c.real_send)
        active = text.replace('provider = "fake"', 'provider = "deepseek"').replace(
            'allow_network = false', 'allow_network = true')
        with self.assertRaises(ConfigError):
            self.load(active)
        c = self.load(active, {'WECHAT_AI_API_KEY':'TEST_ONLY'})
        self.assertEqual(c.model.provider, 'deepseek')
        self.assertNotIn('TEST_ONLY', repr(c))


if __name__ == '__main__':
    unittest.main()
