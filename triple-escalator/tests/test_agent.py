import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from cascade_agent import Bridge, child_environment, configuration, terminate_group
from cascade_session import Session
from cascade_sandbox import profile
from http.server import ThreadingHTTPServer

MODEL = 'deepseek/deepseek-v4.1-flash'
CATALOGUE = {'data': {'endpoints': [{'tag': 'morph/fp8', 'context_length': 1048576,
             'max_completion_tokens': 943718, 'supported_parameters': ['tools', 'max_tokens']}]}}

class Upstream(io.BytesIO):
    def __init__(self, data, content_type):
        super().__init__(data)
        self.headers = {'Content-Type': content_type}

class CodingAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        health = patch("cascade_agent.record_provider_health")
        health.start()
        self.addCleanup(health.stop)
        self.repo = self.root/'repo'; self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo/'app.txt').write_text('before')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','baseline'],check=True)
        self.session = Session.create(self.root/'session',self.repo,'original-parent','inherit','Fix and test')
        self.bridge = Bridge(self.session,'flash','test',MODEL,{'only':['morph'],'ignore':[], 'zdr':True,'data_collection':'deny'},'morph/fp8','high','not-real',CATALOGUE)

    def request(self, data, content_type):
        server = ThreadingHTTPServer(('127.0.0.1',0),self.bridge.handler())
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        # Use an opener bound before patching the upstream transport.
        opener = urllib.request.build_opener()
        req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/chat/completions',data=json.dumps({'model':MODEL,'messages':[{'role':'user','content':'task'}]}).encode(),headers={'Authorization':'Bearer '+self.bridge.token})
        try:
            with patch('cascade_agent.urllib.request.urlopen',return_value=Upstream(data,content_type)):
                with opener.open(req,timeout=5) as response:result=response.read()
            return result
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_wire_overrides_sdk_cap_and_enforces_policy(self):
        body=self.bridge.prepare({'model':MODEL,'messages':[{'role':'user','content':'task'}],'tools':[{'type':'function','function':{'name':'bash'}}],'max_tokens':32000,'provider':{'only':['unapproved']},'reasoning':{'effort':'low'}})
        self.assertEqual(body['max_tokens'],943718)
        self.assertEqual(body['provider']['only'],['morph/fp8'])
        self.assertFalse(body['provider']['allow_fallbacks'])
        self.assertTrue(body['provider']['zdr'])
        self.assertEqual(body['provider']['data_collection'],'deny')
        self.assertEqual(body['reasoning']['effort'],'high')
        self.assertEqual(body['tools'][0]['function']['name'],'bash')

    def test_wire_reserves_context_for_tool_schemas(self):
        from cascade_tokens import input_tokens
        request={'model':MODEL,'messages':[{'role':'user','content':'task'}], 'tools':[{'type':'function','function':{'name':'bash','description':'use this tool ' * 80000}}]}
        expected=input_tokens(MODEL, request)
        body=self.bridge.prepare(request)
        self.assertEqual(body['max_tokens'],1048576-expected)

    def test_model_switch_and_unapproved_provider_fail(self):
        with self.assertRaises(ValueError): self.bridge.prepare({'model':'wrong','messages':[]})
        self.bridge.tag='unapproved/provider'
        with self.assertRaises(ValueError): self.bridge.prepare({'model':MODEL,'messages':[]})

    def test_no_real_credentials_in_harness_environment(self):
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'secret','AWS_SECRET_ACCESS_KEY':'secret','OPENCODE_CONFIG':'host-config'}):
            env=child_environment(self.root,{'provider':{'key':'loopback-only'}})
        for key in ['OPENROUTER_API_KEY','AWS_SECRET_ACCESS_KEY','OPENCODE_CONFIG']: self.assertNotIn(key,env)
        self.assertEqual(env['OPENCODE_DISABLE_PROJECT_CONFIG'],'true')

    def test_truncated_and_empty_json_fail(self):
        for finish,content in [('length','partial'),('stop','')]:
            self.bridge.errors=[]
            self.request(json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content}}]}).encode(),'application/json')
            self.assertTrue(self.bridge.errors)
            self.assertEqual(self.session.events()[-1]['status'],'failed')

    def test_empty_or_unfinished_stream_fails(self):
        for data in [b'data: [DONE]\n\n',b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\ndata: [DONE]\n\n']:
            self.bridge.errors=[]
            received=self.request(data,'text/event-stream')
            self.assertTrue(self.bridge.errors)
            self.assertNotIn(b'[DONE]',received)

    def test_tool_stream_records_real_usage(self):
        chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'tool1','type':'function','function':{'name':'bash','arguments':'{}'}}]},'finish_reason':None}]},
                {'choices':[{'delta':{},'finish_reason':'tool_calls'}]},
                {'choices':[],'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':0.002}}]
        data=b''.join(('data: '+json.dumps(c)+'\n\n').encode() for c in chunks)+b'data: [DONE]\n\n'
        self.assertEqual(self.request(data,'text/event-stream'),data)
        self.assertFalse(self.bridge.errors)
        self.assertEqual(self.session.summary()['known_cost_usd'],0.002)
        self.assertEqual(self.session.summary()['checks_passed'],0)


    def test_flash_policy_defaults_to_max_without_spend_cap(self):
        import cascade_agent
        with patch('sys.argv', ['agent', 'flash', 'task.md', '--session', '/unused', '--task', 'example']), patch.object(cascade_agent, 'run', return_value=0) as execute:
            self.assertEqual(cascade_agent.main(), 0)
        args = execute.call_args.args[0]
        self.assertEqual(args.reasoning, 'max')
        self.assertIsNone(args.budget)
        self.bridge.effort = args.reasoning
        body = self.bridge.prepare({'model': MODEL, 'messages': [{'role': 'user', 'content': 'task'}], 'reasoning': {'effort': 'low'}})
        self.assertEqual(body['reasoning'], {'effort': 'max'})
        self.assertEqual(body['max_tokens'], 943718)

    def test_canary_budget_stops_between_calls_without_token_cap(self):
        self.bridge.budget=0.1;self.bridge.cost=0.1
        with self.assertRaises(ValueError):self.bridge.prepare({'model':MODEL})
        self.bridge.cost=0;self.bridge.unknown=True
        with self.assertRaises(ValueError):self.bridge.prepare({'model':MODEL})

    def test_handoff_includes_worker_report_and_tool_evidence(self):
        self.session.append('coding_result',task='test',worker='flash',report='Fixed Decimal',logs='/private/log')
        self.session.append('worker_tool',task='test',worker='flash',tool='bash',status='completed',input={'command':'python3 -m unittest'},output='Ran 6 tests, OK')
        h=self.session.handoff('test')
        self.assertEqual(h['coding_results'][0]['report'],'Fixed Decimal')
        self.assertIn('Ran 6 tests',h['worker_tools'][0]['output_excerpt'])

    def test_watchdog_kills_term_ignoring_worker(self):
        proc=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(30)'],stdout=subprocess.PIPE,text=True,start_new_session=True)
        self.assertEqual(proc.stdout.readline().strip(),'ready')
        terminate_group(proc,grace=0.1)
        self.assertIsNotNone(proc.poll())
        proc.stdout.close()

    def test_cleanup_kills_descendant_after_leader_exit(self):
        code='import os,signal,time; child=os.fork(); exit(0) if child else None; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("child ready",flush=True); time.sleep(30)'
        proc=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,text=True,start_new_session=True)
        self.assertEqual(proc.stdout.readline().strip(),'child ready')
        proc.wait(timeout=5)
        terminate_group(proc,grace=0.1)
        self.assertEqual(proc.stdout.read(),'')
        proc.stdout.close()

    @unittest.skipUnless(sys.platform=='darwin','macOS sandbox')
    def test_real_sandbox_repo_access_secret_and_outside_denial(self):
        runtime=self.root/'runtime';runtime.mkdir()
        (self.repo/'.env.local').write_text('fixture only')
        (self.repo/'credentials.json').write_text('fixture only')
        outside=self.root/'outside';outside.write_text('fixture only')
        (self.repo/'escape').symlink_to(outside)
        sb=self.root/'profile.sb';sb.write_text(profile(self.repo,runtime,Path('/usr/bin/true'),[65534]))
        def execute(cmd):return subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),'/bin/sh','-c',cmd],cwd=self.repo,capture_output=True)
        self.assertEqual(execute('cat app.txt').returncode,0)
        self.assertEqual(execute('printf after > app.txt').returncode,0)
        for name in ['.env.local','credentials.json','escape',str(outside)]:
            self.assertNotEqual(execute('cat '+name).returncode,0,name)
        self.assertNotEqual(execute('printf x > '+str(outside)).returncode,0)

if __name__=='__main__':unittest.main()
