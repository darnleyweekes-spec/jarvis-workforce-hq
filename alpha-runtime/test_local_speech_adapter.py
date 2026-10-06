import tempfile,unittest,wave,shutil
from pathlib import Path
from alpha_runtime import SpecialistTask,MissionState,MissionError
from local_speech_adapter import speak
class SpeechTests(unittest.TestCase):
    def test_permission(self):
        t=SpecialistTask('t','voice','speak',(),(),(),(),(),MissionState())
        with self.assertRaises(MissionError): speak(t,'test','test.wav')
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_real_wav_and_no_overwrite(self):
        t=SpecialistTask('t','voice','speak',(),(),('speech.local.write',),(),(),MissionState())
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'speech.wav'; speak(t,'Alpha is ready for project work.',p)
            with wave.open(str(p)) as w: self.assertGreater(w.getnframes(),1000)
            with self.assertRaises(MissionError): speak(t,'overwrite',p)
