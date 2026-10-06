"""Offline stock-voice fallback for Chatterbox. No voice cloning."""
from pathlib import Path
import subprocess
import tempfile
from alpha_runtime import MissionError

def speak(task,text,output):
    if 'speech.local.write' not in task.allowed_tools: raise MissionError('Missing speech.local.write')
    if not isinstance(text,str) or not 1<=len(text)<=3000: raise ValueError('Text limit: 3000 characters')
    output=Path(output).resolve()
    if output.exists(): raise MissionError('Output already exists')
    if output.suffix!='.wav': raise ValueError('Expected WAV output')
    with tempfile.TemporaryDirectory(prefix='alpha-speech-') as folder:
        source=Path(folder)/'text.txt'; source.write_text(text)
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','lavfi','-i',f'flite=textfile={source}:voice=slt','-ar','24000',str(output)],check=True,timeout=60)
    return {'path':str(output),'engine':'ffmpeg-flite','voice':'stock-slt','voice_cloning':False}
