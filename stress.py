"""Small concurrent load test for the server's bounded admission control."""
import argparse
import concurrent.futures
import datetime
import json
import pathlib
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave

def percentile(xs, fraction):
    ys=sorted(xs)
    if not ys: return None
    return ys[max(0, round((len(ys)-1)*fraction))]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav')
    parser.add_argument('--language',choices=['zh','en','auto'],default='en')
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--concurrency',type=int,default=8)
    parser.add_argument('--requests',type=int,default=32)
    parser.add_argument('--out',default='results/stress.json')
    a=parser.parse_args()
    if not 2<=a.concurrency<=32 or a.requests<a.concurrency or a.requests>256:
        parser.error('use concurrency 2..32 and requests concurrency..256')
    out=pathlib.Path(a.out)
    if out.exists(): parser.error('output exists; pick a new filename')
    with wave.open(a.wav,'rb') as f:
        if (f.getframerate(),f.getnchannels(),f.getsampwidth()) != (16000,1,2):
            parser.error('WAV must be 16000 Hz, mono, PCM16')
        audio_seconds=f.getnframes()/16000
    if not 0<audio_seconds<=30: parser.error('clip must be <=30s')
    audio=pathlib.Path(a.wav).read_bytes()
    with urllib.request.urlopen(a.url+'/health',timeout=5) as r:
        if json.load(r).get('status')!='ok': raise RuntimeError('server not ready')
    with urllib.request.urlopen(a.url+'/metrics',timeout=5) as r:
        before=json.load(r)
    # Synchronize each wave so requests actually contend, not arrive serially by chance.
    barrier=threading.Barrier(a.concurrency)
    def request(i):
        boundary='mini-stress-'+uuid.uuid4().hex
        fields={'language':a.language,'response_format':'json','temperature':'0.0','temperature_inc':'0.0'}
        chunks=[]
        for key,value in fields.items():
            chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode())
        chunks.extend((audio,f'\r\n--{boundary}--\r\n'.encode()))
        body=b''.join(chunks)
        req=urllib.request.Request(a.url+'/inference',data=body,
             headers={'Content-Type':f'multipart/form-data; boundary={boundary}'},method='POST')
        barrier.wait()
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(req,timeout=180) as r:
                result=json.load(r); status=r.status
        except urllib.error.HTTPError as e:
            status=e.code
            raw=e.read()
            try: result=json.loads(raw)
            except ValueError: result={'error':raw.decode('utf-8','replace')[:300]}
        except Exception as e:
            status=0; result={'error':str(e)}
        return {'id':i,'status':status,'client_ms':(time.perf_counter()-start)*1000,
                'text':result.get('text'),'error':result.get('error'),
                'handler_ms':result.get('handler_ms'),'processing_ms':result.get('processing_ms'),
                'queue_ms':result.get('queue_ms'),'preprocess_ms':result.get('preprocess_ms'),
                'model_wait_ms':result.get('model_wait_ms')}
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        records=list(pool.map(request,range(a.requests)))
    wall=time.perf_counter()-start
    with urllib.request.urlopen(a.url+'/metrics',timeout=5) as r: after=json.load(r)
    success=[x for x in records if x['status']==200]
    rejected=[x for x in records if x['status']==429]
    failed=[x for x in records if x['status'] not in (200,429)]
    successful_latency=[x['client_ms'] for x in success]
    report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'config':{'concurrency':a.concurrency,'requests':a.requests,'audio_seconds':audio_seconds,
                 'language':a.language,'admission_limit':after['max_in_flight']},
       'status_counts':{'200':len(success),'429':len(rejected),'other':len(failed)},
       'failure_rate':len(failed)/a.requests,'overload_rate':len(rejected)/a.requests,
       'wall_seconds':wall,'successful_rps':len(success)/wall,
       'successful_client_ms':{'p50':percentile(successful_latency,.50),'p95':percentile(successful_latency,.95)},
       'metrics_before':before,'metrics_after':after,'requests':records,
       'interpretation':'429 is intentional backpressure. Compare latency only with status counts and rates.'}
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='requests'},ensure_ascii=False,indent=2))
    if len(success)<1 or after['peak_in_flight']>after['max_in_flight']:
        raise SystemExit('load test failed its basic service invariant')

if __name__=='__main__': main()
