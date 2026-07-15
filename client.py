"""Upload PCM WAV to the bundled C++ server. Python standard library only."""
import argparse
import datetime
import hashlib
import json
import pathlib
import statistics
import time
import urllib.error
import urllib.request
import uuid
import wave

def multipart(audio, language):
    boundary='mini-whisper-'+uuid.uuid4().hex
    chunks=[]
    fields={'language':language,'response_format':'json',
            'temperature':'0.0','temperature_inc':'0.0'}
    for name,value in fields.items():
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode())
    chunks.append(audio)
    chunks.append(f'\r\n--{boundary}--\r\n'.encode())
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('wav')
    p.add_argument('--language',choices=['zh','en','auto'],default='zh')
    p.add_argument('--url',default='http://127.0.0.1:8080/inference')
    p.add_argument('--repeat',type=int,default=1)
    p.add_argument('--warmup',type=int,default=0)
    p.add_argument('--out',help='Optional new JSON file; existing files are preserved')
    a=p.parse_args()
    if not 1<=a.repeat<=100 or not 0<=a.warmup<=10: p.error('repeat: 1..100; warmup: 0..10')
    if a.out and pathlib.Path(a.out).exists(): p.error('output already exists; choose another filename')
    path=pathlib.Path(a.wav)
    try:
        with wave.open(str(path),'rb') as f:
            if (f.getnchannels(),f.getsampwidth(),f.getframerate()) != (1,2,16000):
                p.error('WAV must be 16000 Hz, mono, PCM16. See README for ffmpeg conversion.')
            audio_seconds=f.getnframes()/16000
        if not 0<audio_seconds<=30: p.error('use a clip longer than 0 and no longer than 30 seconds')
        audio=path.read_bytes()
        body,ctype=multipart(audio,a.language)
        records=[]
        for i in range(a.warmup+a.repeat):
            start=time.perf_counter()
            request=urllib.request.Request(a.url,data=body,headers={'Content-Type':ctype},method='POST')
            with urllib.request.urlopen(request,timeout=180) as response:
                result=json.load(response)
            elapsed=(time.perf_counter()-start)*1000
            if not isinstance(result.get('text'),str) or not result['text'].strip():
                raise RuntimeError('no transcript returned: '+json.dumps(result,ensure_ascii=False))
            result['client_ms']=elapsed
            if i>=a.warmup:
                records.append(result)
                print(json.dumps(result,ensure_ascii=False))
        report={'mode':'REAL_WHISPER_TINY_CPU','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'wav_sha256':hashlib.sha256(audio).hexdigest(),'audio_seconds':audio_seconds,
                'language':a.language,'warmup_excluded':a.warmup,'repeat':a.repeat,
                'mean_client_ms':statistics.mean(x['client_ms'] for x in records),'requests':records,
                'note':'Sequential requests. Small-sample timing only; no concurrency or accuracy benchmark claim.'}
        if a.out:
            out=pathlib.Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
            with out.open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
        print(f"Mean client latency: {report['mean_client_ms']:.1f} ms; measured requests: {a.repeat}")
    except (OSError,ValueError,RuntimeError,wave.Error) as e:
        raise SystemExit(f'Failed: {e}\nCheck the audio and the terminal running bash start.sh.')

if __name__=='__main__': main()
