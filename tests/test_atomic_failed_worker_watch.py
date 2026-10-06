import unittest

from scripts.atomic.watch_failed_workers import aged_exception


class FailedWorkerWatchTests(unittest.TestCase):
    def snapshot(self,*lines):
        return {'data':{'result':[{'values':[[str(int(t*1e9)),line] for t,line in lines]}]}}

    def test_policy_failure_and_reconnect_cannot_stop_a_worker(self):
        data = self.snapshot((1,'Native task success: False'),
                             (2,'ConnectionClosedError: keepalive ping timeout'),
                             (3,'[atomic contacts] quiet scene; awaiting contact evidence'))
        self.assertIsNone(aged_exception(data,1000))

    def test_explicit_exception_requires_cleanup_grace_in_any_stream_order(self):
        marker = '[Eval] unhandled exception during reset/run_eval: broken tensor'
        data = self.snapshot((150,marker),(100,marker),(50,'normal log'))
        self.assertIsNone(aged_exception(data,399))
        self.assertEqual(aged_exception(data,400),100)
        self.assertIsNone(aged_exception(data,90))

